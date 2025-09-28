'''
This file processes everything related to tuitions
'''

class Subjects(Enum):
    '''
    get enum definitions from db
    '''
    #TODO
    ...

class Tuition(BaseModel):
    """
    A self-contained descriptor for a specific tuition session. 
    """
    students: list[Student]
    subject: Subject
    min_duration: timedelta
    max_duration: timedelta
    lesson_index: int # NEW: Tracks which lesson this is (1, 2, etc.)

    model_config = ConfigDict(frozen=True)


class Tuitions:
    '''
    get all tuition instances from db
    create new tuitions
    edit tuitions
    delete tuitions
    '''
    #
