import os.path
import datetime as dt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# The scope allows the script to read and write events to your calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class GoogleCalendarMeet:
    """
    This class manages Google Meets and calendar events.
    It handles authentication and provides methods to create, find, update, and delete events.
    """
    def __init__(self):
        """
        Initializes the class and authenticates with the Google Calendar API.
        """
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        try:
            self.service = build("calendar", "v3", credentials=creds)
            print("Successfully connected to Google Calendar API.")
        except HttpError as error:
            print(f"An error occurred during connection: {error}")
            self.service = None

    def _find_event(self, summary, start_time_iso):
        """
        Finds an event by its summary (name) and exact start time.
        Returns the event object if found, otherwise None.
        """
        if not self.service:
            return None
            
        # Google API requires time in RFC3339 format, which is what isoformat() produces.
        # We search in a one-minute window around the start time to be safe.
        start_time_dt = dt.datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))
        time_min = (start_time_dt - dt.timedelta(seconds=30)).isoformat() + 'Z'
        time_max = (start_time_dt + dt.timedelta(seconds=30)).isoformat() + 'Z'

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    q=summary, # Search by text (summary/name)
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            
            # The search 'q' is broad, so we need to find the exact match
            for event in events:
                if event['summary'] == summary and event['start'].get('dateTime') == start_time_iso:
                    print(f"Found existing event: '{summary}' with ID: {event['id']}")
                    return event
            return None
        except HttpError as error:
            print(f"An error occurred while searching for events: {error}")
            return None

    def create_meet_link_and_calendar_event(self, summary, start_time_iso, end_time_iso, timezone='Africa/Cairo'):
        """
        Creates a new Google Calendar event with a Google Meet link.

        Returns:
            dict: The created event object, including the eventId and meet link.
        """
        if not self.service:
            return None

        event_body = {
            'summary': summary,
            'start': {'dateTime': start_time_iso, 'timeZone': timezone},
            'end': {'dateTime': end_time_iso, 'timeZone': timezone},
            'conferenceData': {
                'createRequest': {
                    'requestId': f"{summary}-{start_time_iso}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
        }

        try:
            created_event = self.service.events().insert(
                calendarId='primary', 
                body=event_body,
                conferenceDataVersion=1
            ).execute()
            
            print(f"\n🎉 Successfully created event: '{summary}'")
            print(f"   Meet Link: {created_event.get('hangoutLink')}")
            print(f"   Event ID: {created_event.get('id')}")
            return created_event
        except HttpError as error:
            print(f"An error occurred while creating the event: {error}")
            return None

    def delete_calendar_event(self, summary, start_time_iso):
        """
        Finds and deletes a specific calendar event.
        """
        event_to_delete = self._find_event(summary, start_time_iso)

        if not event_to_delete:
            print(f"Could not find event '{summary}' at {start_time_iso} to delete.")
            return

        try:
            self.service.events().delete(
                calendarId='primary', 
                eventId=event_to_delete['id']
            ).execute()
            print(f"🗑️ Successfully deleted event: '{summary}'")
        except HttpError as error:
            print(f"An error occurred while deleting the event: {error}")

    def create_or_update_event(self, summary, start_time_iso, end_time_iso, timezone='Africa/Cairo'):
        """
        Checks if an event exists. If it does, it updates it. If not, it creates it.
        This is a more powerful version of your 'check_calendar_event'.
        """
        existing_event = self._find_event(summary, start_time_iso)

        if existing_event:
            # Event exists, check if end time needs updating
            if existing_event['end'].get('dateTime') != end_time_iso:
                print(f"Updating event '{summary}'...")
                existing_event['end']['dateTime'] = end_time_iso
                try:
                    updated_event = self.service.events().update(
                        calendarId='primary',
                        eventId=existing_event['id'],
                        body=existing_event
                    ).execute()
                    print("✅ Event updated successfully.")
                    return updated_event
                except HttpError as error:
                    print(f"An error occurred while updating the event: {error}")
                    return None
            else:
                print(f"Event '{summary}' is already up-to-date.")
                return existing_event
        else:
            # Event does not exist, create it
            print(f"No existing event found for '{summary}'. Creating a new one.")
            return self.create_meet_link_and_calendar_event(summary, start_time_iso, end_time_iso, timezone)


# --- EXAMPLE USAGE ---
if __name__ == "__main__":
    # 1. Initialize the manager
    manager = GoogleCalendarMeet()

    if manager.service:
        # 2. Define event details (using UTC for consistency)
        start_time = dt.datetime.utcnow() + dt.timedelta(days=1)
        end_time = start_time + dt.timedelta(hours=1)
        
        start_iso = start_time.isoformat() + 'Z' # 'Z' indicates UTC time
        end_iso = end_time.isoformat() + 'Z'
        
        event_name = "Team Strategy Session"

        # 3. Create or Update the event
        print("\n--- Running Create or Update ---")
        manager.create_or_update_event(event_name, start_iso, end_iso)
        
        # 4. Run it again to show it's up-to-date
        print("\n--- Running Create or Update Again (should find existing) ---")
        manager.create_or_update_event(event_name, start_iso, end_iso)

        # 5. Delete the event
        print("\n--- Running Delete ---")
        manager.delete_calendar_event(event_name, start_iso)
        
        # 6. Verify it's gone
        print("\n--- Verifying Deletion ---")
        manager._find_event(event_name, start_iso)

    else:
        print('no')
