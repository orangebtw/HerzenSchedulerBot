import requests
import bs4
from dataclasses import dataclass
from datetime import datetime, time
import re

import utils

HERZEN_URL = "https://old-guide.herzen.spb.ru"
GROUPS_URL = f"{HERZEN_URL}/static/schedule.php"
SCHEDULE_DATA_URL = f"{HERZEN_URL}/static/schedule_dates.php"

@dataclass(frozen=True)
class ScheduleGroup:
    name: str
    id: str

@dataclass(frozen=True)
class ScheduleCourse:
    name: str
    groups: list[ScheduleGroup]

@dataclass(frozen=True)
class ScheduleStage:
    name: str
    courses: list[ScheduleCourse]

@dataclass(frozen=True)
class ScheduleForm:
    name: str
    stages: list[ScheduleStage]

@dataclass(frozen=True)
class ScheduleFaculty:
    name: str
    # course: str
    # stage: str
    # group: str
    index: int
    forms: list[ScheduleForm]

@dataclass(frozen=True)
class ScheduleSubject:
    time_start: datetime
    time_end: datetime
    mod: str
    name: str
    type: str
    teacher: str
    room: str

@dataclass(frozen=True)
class Schedule:
    id: ScheduleFaculty
    subjects: list[ScheduleSubject]

def parse_groups() -> list[ScheduleFaculty]:
    res = requests.get(GROUPS_URL, {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    })
    assert(res.status_code == 200)
    bs = bs4.BeautifulSoup(res.content, "html.parser")
    
    schedule_ids: list[ScheduleFaculty] = []
    index = 0
    for faculty in bs.find('h1').find_next_siblings('h3'):
        forms: list[ScheduleForm] = []
        for education_form in faculty.find_next_sibling('div').find_all('h4'):
            form = {}
            
            for data in education_form.find_next_sibling('ul').find_all('li'):
                id_div = data.div
                group_id = data.find('div').find('button')['onclick']
                group_id = group_id.split("'")[1].split('=')[1].split('&')[0]
                id_div.decompose()
                stage, course, group = data.text.strip().split(', ')
                
                if stage not in form.keys():
                    form[stage] = {}
                    form[stage][course] = {}
                    form[stage][course][group] = group_id
                elif course not in form[stage].keys():
                    form[stage][course] = {}
                    form[stage][course][group] = group_id
                else:
                    form[stage][course][group] = group_id
                    
            stages: list[ScheduleStage] = []
            for stage_name, value in form.items():
                courses: list[ScheduleCourse] = []
                for course_name, course in value.items():
                    groups: list[ScheduleGroup] = []
                    for group_name, group_id in course.items():
                        groups.append(ScheduleGroup(group_name.removeprefix("группа "), group_id))
                    courses.append(ScheduleCourse(course_name, groups))
                stages.append(ScheduleStage(stage_name, courses)) 
            forms.append(ScheduleForm(education_form.text, stages))
        # schedule_ids.append(ScheduleId(faculty.text, course, stage, group.removeprefix("группа "), group_id))
        schedule_ids.append(ScheduleFaculty(faculty.text, index, forms))
        index += 1
    return schedule_ids

def parse_schedule(group_id: str, subgroup_id: int | None = None) -> list[ScheduleSubject] | None:
    res = requests.get(f"{SCHEDULE_DATA_URL}?id_group={group_id}", {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    })
    assert(res.status_code == 200)
    
    bs = bs4.BeautifulSoup(res.content, "html.parser")
    
    if bs.find('a', string='другую группу'):  # No classes at that period
    #     last_summer_day = datetime.datetime(date_1.year, 8, 31).date()
    #     if date_1 <= last_summer_day < date_2:
    #         return parse_date_schedule(group_id, subgroup_id, last_summer_day + datetime.timedelta(days=1), date_2)
        return None
    
    if bs.find('tbody'):
        courses_column = bs.find('tbody').find_all('tr')
    else:
        return None

    schedule_courses: list[ScheduleSubject] = []
    day_name = ''
    for class_number in range(len(courses_column)):

        class_time = str(courses_column[class_number].find('th').text)

        if courses_column[class_number].find('th', {'class': 'dayname'}):
            day_name = courses_column[class_number].find('th', {'class': 'dayname'}).text
            continue

        course = courses_column[class_number].find_all('td')

        if (len(course) > 1) and subgroup_id and (0 < subgroup_id <= len(course)):  # If multiple classes at the same time
            course = course[subgroup_id - 1]
        else:
            course = course[0]

        if not course.find('strong'):  # If class not found
            continue
        
        class_names = course.find_all('strong')
        for class_name in class_names:
            class_type = class_name.next.next

            if class_name.find('br'):
                class_type = class_type.next.next
            if type(class_name.next) is not bs4.NavigableString:
                class_type = class_type.next

            class_mod = class_type.next.next
            if type(class_mod) is not bs4.NavigableString:
                class_mod = ''
            else:
                class_mod = class_mod.text.strip()
                class_mod = re.sub(r'(\d\d\.\d\d—\d\d\.\d\d)|'
                                   r'(\d\.\d\d—\d\.\d\d)|'
                                   r'(\d\.\d\d—\d\d\.\d\d)|'
                                   r'(\d\d\.\d\d—\d\.\d\d)|'
                                   r'(\d\d\.\d\d)|(\d\.\d\d)', '', class_mod)
                class_mod = re.sub(r'(\()|(\))|(\* дистанционное обучение)', '', class_mod)
                class_mod = class_mod.strip()

            class_teacher = ''
            class_room = ''

            if "дистанционное обучение" not in course.text:
                class_teacher = class_type.next.next.next
                class_room = class_teacher.next.next

                class_teacher = class_teacher.text
                class_room = str(class_room.text).strip(", \n")
                
            date_str = day_name.split(',')[0].strip()
            date = datetime.strptime(date_str, "%d.%m.%Y")
            
            time_start_str, time_end_str = str(class_time).split('—')
            
            time_start_h, time_start_m = time_start_str.strip().split(':')
            time_end_h, time_end_m = time_end_str.strip().split(':')
            
            time_start = time(hour=int(time_start_h), minute=int(time_start_m))
            time_end = time(hour=int(time_end_h), minute=int(time_end_m))
            
            date_start = datetime.combine(date, time_start, tzinfo=utils.DEFAULT_TIMEZONE)
            date_end = datetime.combine(date, time_end, tzinfo=utils.DEFAULT_TIMEZONE)

            schedule_courses.append(ScheduleSubject(
                time_start=date_start,
                time_end=date_end,
                mod=class_mod,
                name=class_name.text.strip(),
                type=class_type.strip(),
                teacher=class_teacher.strip(),
                room=class_room
            ))
    return schedule_courses


if __name__ == "__main__":
    schedules = parse_groups()
    subjects = parse_schedule(schedules[0].forms[0].stages[0].courses[0].groups[0].id)
    print(subjects[0])
    # for g in groups:
    #     print(g)

    # for g in groups:
    #     print(f"{g.faculty}:")
    #     for f in g.forms:
    #         print("  ", end="")
    #         print(f.name)
    #         for s in f.stages:
    #             print("    ", end="")
    #             print(s.name)
    #             for c in s.courses:
    #                 print("      ", end="")
    #                 print(c.name)
    #                 for g in c.groups:
    #                     print("        ", end="")
    #                     print(g)
    # group = next(x for x in schedules if x.forms == "2об_ИВТ-2")
    # subjects = parse_schedule(group.id)
    # for subject in subjects:
    #     print(subject)
