# 🚀 Final Master Architecture: Notification System

## 1. Architectural Overview

* **Pattern:** Server-Centric, Event-Driven, Topic-Based.
* **Frontend Role:** "Dumb" Client. Responsible only for sending the Device Token to the backend and handling "Tap" actions.
* **Backend Role:** "Source of Truth." Manages all subscription logic (Who listens to what).
* **Transport:** Firebase Cloud Messaging (FCM).
* **Concurrency:** All FCM network calls within FastAPI are executed as **`BackgroundTasks`** to prevent blocking the main API thread.
* **Topic Schema:**
    * `user_{user_uuid}`: Reaches all devices belonging to a specific user.
    * `tuition_{tuition_uuid}`: Reaches all users enrolled in a specific tuition.

---

## 2. Phase 1: Device Registration (The Bootstrap)
*Goal: Populate the empty `user_devices` table and sync subscriptions immediately upon user activity.*

### A. Frontend (Capacitor)
* **Platform Check Logic:**
    * Before initializing any notification logic, check if the app is running on a Native Platform (iOS/Android).
    * **Instruction:** If the platform is *not* native (i.e., Web/Safari), disable all notification listeners to prevent errors and duplicate logic.
    * *Example Snippet:*
      ```javascript
      import { Capacitor } from '@capacitor/core';
      if (Capacitor.isNativePlatform()) {
          // Initialize listeners here
      }
      ```

* **Registration Listener Logic:**
    * Attach a listener to the `registration` event.
    * **Trigger:** This event fires automatically on App Install, First Launch, or if the Operating System decides to rotate the token.
    * **Action:** Call the backend endpoint `POST /users/notifications` with the new token payload.
    * *Example Snippet:*
      ```javascript
      PushNotifications.addListener('registration', (token) => {
          api.post('/users/notifications', { token: token.value });
      });
      ```

* **Action Performed Logic (Handling Taps):**
    * Attach a listener to the `pushNotificationActionPerformed` event.
    * **Trigger:** This fires when a user taps on a notification banner while the app is in the background or closed.
    * **Action:** Extract the `data` object from the payload and switch based on the `action` key (e.g., 'open_tuition' vs 'open_profile') to redirect the router.
    * *Example Snippet:*
      ```javascript
      PushNotifications.addListener('pushNotificationActionPerformed', (notification) => {
          const data = notification.notification.data;
          if (data.action === 'open_tuition') {
              router.navigate(`/tuition/${data.tuition_id}`);
          }
          if (data.action === 'open_profile') {
              router.navigate(`/profile`);
          }
      });
      ```

### B. Backend (`POST /users/notifications`)
* **Request:** `{ token: str }`
* **Step 1 (Database):**
    * **Upsert** into `user_devices` table:
        * Columns: `user_id`, `token`, `platform` (ios/android), `last_updated`.
        * *Logic:* If token exists, update timestamp. If new, insert.
* **Step 2 (Sync Logic - via BackgroundTask):**
    * **Task:** `sync_subscriptions(user_uuid, token)`
    * **Action A:** Call `FCM.subscribe_to_topic(token, f"user_{user_uuid}")`.
    * **Action B:** Query database for all **active** tuitions for this user.
    * **Action C:** Call `FCM.subscribe_to_topic(token, [list_of_tuition_uuids])`.
* **Result:** The user is now fully reachable on this specific device.

---

## 3. Phase 2: Enrollment Management (State Changes)
*Goal: Automatically update subscriptions when a student's schedule changes.*

* **Trigger:** Any API endpoint that triggers `TuitionService.regenerate_all_tuitions()`.
* **Step 1: Pre-Calculation (Inside DB Transaction)**
    * Create a memory map of the *Current State*: `{ UserUUID: [Set_of_TuitionUUIDs] }`.
* **Step 2: Execution (Inside DB Transaction)**
    * Truncate `tuitions` table.
    * Regenerate/Insert new tuition data based on complex logic.
    * **COMMIT Transaction.** (Lock released).
* **Step 3: Diffing (Post-Transaction)**
    * Compare *New State* vs *Old State*.
    * Identify **New** Tuition UUIDs for each User.
* **Step 4: Async Sync (via BackgroundTask)**
    * For every user with **New** tuitions:
        * Fetch their tokens from `user_devices`.
        * Call `FCM.subscribe_to_topic(tokens, f"tuition_{new_uuid}")`.
    * *Note:* We intentionally skip unsubscribing from deleted tuition UUIDs. Google auto-cleans empty topics, and those UUIDs will never be used again.

---

## 4. Phase 3: The Notification Triggers

### The Universal "Safe Send" Logic
*Applicable to all triggers below.*

* **Goal:** Prevent the application from crashing if a message is sent to an uninstalled app or invalid token.
* **Instruction:** Wrap the FCM send call in a `try/except` block.
* **Error Handling:** Specifically catch the `messaging.UnregisteredError`. If this error occurs when sending to a specific token (not a topic), trigger immediate cleanup of that token from the database.
* *Example Snippet, (please note this is a very very simple implementation, in reality, we need a comprehensive service to handl fcm communication with all its details and errors):*
  ```python
  def safe_send_fcm(topic_name, data):
      try:
          response = messaging.send(Message(topic=topic_name, ...))
      except messaging.UnregisteredError:
          # Log error or perform cleanup if target was a specific token
          pass
      except Exception as e:
          log_error(e)
  ```

### Part A: Manual Real-Time Pings
*Goal: Allow Admin/Teachers to ping a whole class or a specific user.*

#### Endpoint 1: Ping Tuition
* **Route:** `POST /notify/tuition/{uuid}`
* **Payload:** `{ "title": "...", "body": "..." }`
* **Logic:**
    * Validate permissions (Teacher owns this tuition).
    * **Action (BackgroundTask):** Send FCM Message to topic `tuition_{uuid}`.
    * **FCM Data Payload:** `{ "action": "open_tuition", "tuition_id": "{uuid}" }`

#### Endpoint 2: Ping User
* **Route:** `POST /notify/user/{uuid}`
* **Payload:** `{ "title": "...", "body": "..." }`
* **Logic:**
    * Validate permissions.
    * **Action (BackgroundTask):** Send FCM Message to topic `user_{uuid}`.
    * **Note:** This automatically reaches **ALL** devices (iPad, iPhone) logged in by that user because they are all subscribed to this topic in Phase 1.
    * **FCM Data Payload:** `{ "action": "open_profile", "user_id": "{uuid}" }`

### Part B: Scheduled Notifications (The Poller)
*Goal: "Class starting in 10 minutes."*

* **Component:** **Separate Python Process** (e.g., `scheduler.py`).
* **Deployment:** Runs alongside the main FastAPI app (e.g., in a separate Docker container or Supervisor process).
* **Mechanism:** Infinite `while True` loop that runs every minute (for example, `asyncio.sleep(60)`).
* **Logic:**
    1.  Calculate `target_time = NOW() + 10 mins`.
    2.  Query DB: `SELECT uuid, name FROM slots WHERE start_time = target_time`.
    3.  **Action:** Iterate results -> `await FCM.send(topic=f"tuition_{uuid}", ...)`
    4.  *Note:* Since this is a standalone script, `await` is used directly (no FastAPI BackgroundTasks needed).

### Part C: Event-Based Notifications (Zoom Webhooks)
*Goal: "Class Started" (Teacher Joined) and "Class Ended".*

#### Endpoint: `POST /webhooks/zoom`
* **Trigger:** Zoom calls this endpoint for `meeting.participant_joined` and `meeting.ended`.
* **Logic:**
    1.  **Security:** Verify the `x-zm-signature` header from Zoom.
    2.  **Scenario 1: Participant Joined**
        * Check Payload: Is `payload.participant_id` == `tuition.teacher_zoom_id`?
        * **If Yes (BackgroundTask):** Send "Class Started" notification to topic `tuition_{uuid}`.
        * **Data Payload:** `{ "action": "join_zoom", "url": "..." }`
        * **If No:** Ignore (Student joined).
    3.  **Scenario 2: Meeting Ended**
        * Check Payload: Is event `meeting.ended`?
        * **Action (BackgroundTask):** Send "Class Finished" notification to topic `tuition_{uuid}`.
        * **Data Payload:** `{ "action": "<sth>", "tuition_id": "{uuid}" }`

---

## 5. Phase 4: Maintenance (The Reaper)
*Goal: Clean up "Zombie Tokens" (Lost phones, uninstalled apps) to maintain DB hygiene.*

* **Component:** Add a function to `scheduler.py`.
* **Frequency:** Run once every 24 hours.
* **Logic:**
    * Execute a database query to delete tokens that have not performed a Phase 1 "Check In" recently.
    * **Condition:** `last_updated < NOW() - INTERVAL '6 months'`.

---

## 6. Phase 5: Session Cleanup (Logout)
*Goal: Stop notifications when a user signs out of a specific device.*

* **Frontend:**
    * User clicks "Logout".
    * App calls `POST /users/logout` with `{ token: "current_device_token" }`.
* **Backend (`POST /users/logout`):**
    * **DB Action:** Delete the row matching `{ token: ... }` from `user_devices`.
    * **Async Action (BackgroundTask):**
        * Call `FCM.unsubscribe_from_topic(token, f"user_{user_uuid}")`.
        * Loop through their active tuitions and unsubscribe from `tuition_{uuid}` as well.
* **Result:** This specific device stops ringing. If the user is logged in on an iPad (different token), the iPad continues to work.

---

## 6. Summary of Endpoints

| HTTP Method | Endpoint | Responsibility | Background Task? |
| :--- | :--- | :--- | :--- |
| **POST** | `/users/notifications` | Register/Update Device Token | **Yes** (Sync Topics) |
| **POST** | `/users/logout` | Remove Device Token | **Yes** (Unsub Topics) |
| **POST** | `/notify/tuition/{id}` | Manual Ping (Whole Class) | **Yes** (Send FCM) |
| **POST** | `/notify/user/{id}` | Manual Ping (Specific User) | **Yes** (Send FCM) |
| **POST** | `/webhooks/zoom` | Handle Zoom Events | **Yes** (Send FCM) |

