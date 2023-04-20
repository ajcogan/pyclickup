"""
models for each object in the clickup api
"""
import json
from datetime import datetime,timedelta
from pyclickup.globals import DEFAULT_STATUSES, LIBRARY
from pyclickup.models.error import MissingClient
from pyclickup.utils.text import snakeify, ts_to_datetime, datetime_to_ts
from requests.models import Response
from typing import Any, Dict, List as ListType, Union  # noqa


class BaseModel:
    """basic model that just parses camelCase json to snake_case keys"""

    def __init__(self, data: dict, client: Any = None, **kwargs: Any) -> None:
        """constructor"""
        self.id = None  # pylint: disable=invalid-name
        self._data = {**data, **kwargs}
        self._json = self._jsond(data)
        self._client = client

        for key in self._data:
            setattr(self, snakeify(key), self._data[key])

    def _jsond(self, json_data: dict) -> str:
        """json dumps"""
        return json.dumps(json_data)

    def _jsonl(self, dictionary: str) -> dict:
        """json loads"""
        return json.loads(dictionary)


class User(BaseModel):
    """user object"""

    def __init__(self, data: dict, **kwargs: Any) -> None:
        """override"""
        if "user" in data.keys():
            data = data["user"]
        super().__init__(data, **kwargs)

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.User[{self.id}] '{self.username}'>"


class Status(BaseModel):
    """status model"""

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.Status[{self.orderindex}] '{self.status}'>"


class List(BaseModel):
    """List model"""

    def __init__(self, data: dict, **kwargs: Any) -> None:
        """override"""
        self.name = ""
        super().__init__(data, **kwargs)

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.List[{self.id}] '{self.name}'>"

    def rename(self, new_name: str) -> Response:
        """renames a list"""
        if not self._client:
            raise MissingClient()
        rename_call = self._client.put(f"list/{self.id}", data={"name": new_name})
        self.name = new_name
        return rename_call

    def get_tasks(self, **kwargs) -> ListType["Task"]:
        """gets tasks for the list"""
        if not self._client:
            raise MissingClient()
        return self._client._get_tasks(
            self.project.space.team.id, list_ids=[self.id], **kwargs  # type: ignore
        )

    def get_all_tasks(self, **kwargs) -> ListType["Task"]:
        """gets every task for this list"""
        if not self._client:
            raise MissingClient()
        return self._client._get_all_tasks(
            self.project.space.team.id, list_ids=[self.id], **kwargs  # type: ignore
        )

    def create_task(
        self,
        name: str,  # string
        content: str = "",  # optional, but nice
        assignees: ListType[Union[int, User]] = None,  # list of User objects, or ints
        status: str = "Open",  # needs to match your given statuses for the list
        priority: int = 0,  # default to no priority (0). check Task class for enum
        due_date: Union[int, datetime] = None,  # integer posix time, or python datetime
    ) -> Union[list, dict, Response]:
        """
        creates a task within this list, returning the id of the task.

        unfortunately right now, there is no way to retreive a task by id
        this will return the ID of the newly created task,
        but you'll need to re-query the list for tasks to get the task object
        """
        if not self._client:
            raise MissingClient()
        task_data = {
            "name": name,
            "content": content,
            "status": status,
        }  # type: Dict[str, Any]

        if assignees:
            task_data["assignees"] = [
                x if isinstance(x, int) else x.id for x in assignees
            ]

        if due_date:
            task_data["due_date"] = (
                due_date if isinstance(due_date, int) else datetime_to_ts(due_date)
            )

        if priority > 0:
            task_data["priority"] = priority

        new_task_call = self._client.post(f"list/{self.id}/task", data=task_data)
        return new_task_call["id"]

    def add_task(
        self,
        task_id: str  # string
    ) -> Union[list, dict, Response]:
        """
        Links existing task with an existing list.

        Added Ash Cogan
        """
        if not self._client:
            raise MissingClient()

        add_task_call = self._client.post(
            "list/{}/task/{}".format(self.id, task_id), data={}
        )

        return True


class Project(BaseModel):
    """project model"""

    def __init__(self, data, **kwargs):
        """override to parse the members"""
        super().__init__(data, **kwargs)
        if self.override_statuses:
            self.statuses = (
                [Status(x, client=self._client, project=self) for x in self.statuses]
                if self.statuses
                else []
            )
        else:
            self.statuses = [
                Status(x, client=self._client, project=self) for x in DEFAULT_STATUSES
            ]
        self.lists = [List(x, client=self._client, project=self) for x in self.lists]

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.Project[{self.id}] '{self.name}'>"

    def create_list(self, list_name: str) -> List:
        """creates a new list in this project: TODO get it updating"""
        if not self._client:
            raise MissingClient()
        new_list = self._client.post(
            f"project/{self.id}/list", data={"name": list_name}
        )
        return new_list

    def get_list(self, list_id: str) -> List:
        """
        gets a list by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self.lists if x.id == list_id][0]

    def get_list_name(self, list_name: str) -> List:
        """
        gets a list by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self.lists if x.name == list_name][0]

    def get_tasks(self, **kwargs):
        """gets tasks for the project"""
        return self._client._get_tasks(
            self.space.team.id, project_ids=[self.id], **kwargs
        )

    def get_all_tasks(self, **kwargs):
        """gets all of the tasks for the project"""
        return self._client._get_all_tasks(
            self.space.team.id, project_ids=[self.id], **kwargs
        )


class Space(BaseModel):
    """space model"""

    def __init__(self, data, **kwargs):
        """override to parse the members and statuses"""
        super().__init__(data, **kwargs)
        self.statuses = [
            Status(x, client=self._client, space=self) for x in self.statuses
        ]
        self._projects = None

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.Space[{self.id}] '{self.name}'>"

    @property
    def projects(self):
        """get the list of projects in the space"""
        if not self._projects or not self._client.cache:
            self._projects = [
                Project(x, client=self._client, space=self)
                for x in self._client.get("space/{}/folder".format(self.id))[
                    "folders"
                ]
            ]
        return self._projects

    def get_project(self, project_id: str) -> Project:
        """
        gets a project by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self.projects if x.id == project_id][0]

    def get_tasks(self, **kwargs):
        """gets tasks for the space"""
        return self._client._get_tasks(self.team.id, space_ids=[self.id], **kwargs)

    def get_all_tasks(self, **kwargs):
        """gets all the tasks for the space"""
        return self._client._get_all_tasks(self.team.id, space_ids=[self.id], **kwargs)


class Team(BaseModel):
    """team object"""

    def __init__(self, data, **kwargs):
        """override to parse the members"""
        super().__init__(data, **kwargs)
        self.members = [User(x, client=self._client, team=self) for x in self.members]
        self._spaces = None

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.Team[{self.id}] '{self.name}'>"

    @property
    def spaces(self):
        """gets a list of all the spaces in this team"""
        if not self._spaces or not self._client.cache:
            self._spaces = [
                Space(x, client=self._client, team=self)
                for x in self._client.get(f"team/{self.id}/space")["spaces"]
            ]
        return self._spaces

    def get_space(self, space_id: str) -> Space:
        """
        gets a space by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self.spaces if x.id == space_id][0]
    
    def get_space_name(self, space_name: str) -> Space:
        """
        gets a space by it's name.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self.spaces if x.name == space_name][0]

    def get_tasks(self, **kwargs):
        """gets tasks for the team"""
        return self._client._get_tasks(self.id, **kwargs)

    def get_all_tasks(self, **kwargs):
        """gets all of the tasks for the team"""
        return self._client._get_all_tasks(self.id, **kwargs)


class Tag(BaseModel):
    """Tag object"""

    def __repr__(self):
        """repr"""
        return f"<{LIBRARY}.Tag '{self.name}'>"


class Task(BaseModel):
    """Task object"""

    class Priority:
        """task priority enum"""

        NONE = 0
        URGENT = 1
        HIGH = 2
        NORMAL = 3
        LOW = 4

    def __init__(self, data, **kwargs):
        """override to parse the data"""
        super(Task, self).__init__(data, **kwargs)

        self.timezone = timedelta(hours=8)

        self.creator = User(self.creator, client=self._client)
        self.status = Status(self.status, client=self._client)
        self.tags = [Tag(x) for x in self.tags]
        self.assignees = [User(x, client=self._client) for x in self.assignees]
        self.due_date = ts_to_datetime(self.due_date) if self.due_date else None
        self.start_date = ts_to_datetime(self.start_date) if self.start_date else None
        self.date_created = (
            ts_to_datetime(self.date_created) if self.date_created else None
        )
        self.date_updated = (
            ts_to_datetime(self.date_updated) if self.date_updated else None
        )
        self.date_closed = (
            ts_to_datetime(self.date_closed) if self.date_closed else None
        )

        # Addition for timezome corrected dates
        self.tz_due_date = (self.due_date + self.timezone).date() if self.due_date else None
        self.tz_start_date = (self.start_date + self.timezone).date() if self.start_date else None
        self.tz_date_created = (
            (self.date_created + self.timezone).date() if self.date_created else None
        )
        self.tz_date_updated = (
            (self.date_updated + self.timezone).date() if self.date_updated else None
        )
        self.tz_date_closed = (
            (self.date_closed + self.timezone).date() if self.date_closed else None
        )


    def __repr__(self):
        """repr"""
        return "<{}.Task[{}] '{}'>".format(LIBRARY, self.id, self.name)

    def get_custom_field(self, field_name):
        """
        gets a list by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """
        return [x for x in self._data['custom_fields'] if x['name'] == field_name][0]

    def get_custom_value(self, field_name, key='value'):
        """
        gets a list by it's ID.
        Currently there is no get API call for this, so until API v2 is live,
        we have to do these this way
        """

        data = [x for x in self._data['custom_fields'] if x['name'] == field_name][0]

        if key in data:

            if data['type'] == 'date':

                return ts_to_datetime(data[key])

            elif data['type'] == 'short_text' or data['type'] == 'long_text':

                return data[key]

            elif data['type'] == 'checkbox':

                return bool(data[key])

    def get_custom_field_id(self, field_name):

        data = [x for x in self._data['custom_fields'] if x['name'] == field_name][0]

        return data["id"]

    def is_key_task(self):

        if self.get_custom_value("Key Planning"):
            return True
        else:
            return False

    def list_tags(self):
        return [x["name"] for x in self._data["tags"]]
    
    def has_tag(self,tag):
        if tag in [x["name"] for x in self._data["tags"]]:
            return True
        else:
            return False
       
    def show_list(self):
        return self._data["list"]["name"]
    
    def update(
        self,
        name: str = None,  # string
        content: str = None,  # string
        add_assignees: ListType[Union[int, User]] = None,
        remove_assignees: ListType[Union[int, User]] = None,
        status: str = None,  # string
        priority: int = None,  # integer
        due_date: Union[int, datetime] = None,  # integer posix time, or python datetime
    ) -> Union[list, dict, Response]:
        """updates the task"""
        if not self._client:
            raise MissingClient()
        if not add_assignees:
            add_assignees = []
        if not remove_assignees:
            remove_assignees = []
        path = f"task/{self.id}"
        data = {
            "assignees": {
                "add": [x if isinstance(x, int) else x.id for x in add_assignees],
                "rem": [x if isinstance(x, int) else x.id for x in remove_assignees],
            }
        }  # type: Dict[str, Any]

        if name:
            data["name"] = name
        if content:
            data["content"] = content
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        if due_date:
            data["due_date"] = (
                due_date if isinstance(due_date, int) else datetime_to_ts(due_date)
            )

        return self._client.put(path, data=data)

    def update_custom_field(self, field, value):
        id = self.get_custom_field_id(field)
        path = "task/{}/field/{}".format(self.id,id)
        data = {"value": value}

        return self._client.post(path, data=data)

    def delete_custom_field(self, field):
        id = self.get_custom_field_id(field)
        path = "task/{}/field/{}".format(self.id,id)
        data = {}

        return self._client.delete(path, data=data)
