from dataclasses import dataclass, field, asdict
import base64
import pprint

import adsk.core
from ...lib.fusion360utils import app, ui
from ...lib import fusion360utils as fus
from ... import config


def b64_url_safe_encode(string):
    encoded_bytes = base64.urlsafe_b64encode(string.encode("utf-8"))
    encoded_str = str(encoded_bytes, "utf-8")
    return encoded_str.rstrip("=")


def b64_url_safe_decode(string):
    return str(base64.urlsafe_b64decode(string.lstrip('a.') + "==="), "utf-8")


def link_for_url(url: str) -> str:
    return f"<a href={url}>{url}</a>"


@dataclass
class FusionData:
    # This should be set at creation or at least validity checked BEFORE calling this
    data_file: adsk.core.DataFile = field(repr=False, default=app.activeDocument.dataFile)

    # THe following are computed based on current state of Fusion and are not "printed" by default
    hub: adsk.core.DataHub = field(repr=False, init=False)
    project: adsk.core.DataProject = field(repr=False, init=False)
    folder: adsk.core.DataFolder = field(repr=False, init=False)
    user: adsk.core.User = field(repr=False, init=False)

    # All String Properties
    file_name: str = field(init=False)
    user_email: str = field(init=False)
    hub_name: str = field(init=False)
    hub_id: str = field(init=False)
    hub_id_decoded: str = field(init=False)
    hub_team_name: str = field(init=False)
    project_name: str = field(init=False)
    project_id: str = field(init=False)
    project_id_decoded: str = field(init=False)
    folder_name: str = field(init=False)
    folder_id: str = field(init=False)
    lineage_urn: str = field(init=False)
    version_urn: str = field(init=False)
    base64_lineage_urn: str = field(init=False)
    base64_version_urn: str = field(init=False)
    open_from_web: str = field(init=False)
    fusion_team_url: str = field(init=False)
    fusion_team_link: str = field(init=False)

    def __post_init__(self):
        # THe following are computed based on current state of Fusion and are not "printed" by default
        self.hub = app.data.activeHub
        self.project = self.data_file.parentProject
        self.folder = self.data_file.parentFolder
        self.user = app.currentUser

        # All String Properties
        self.file_name: str = self.data_file.name
        self.user_email: str = self.user.email
        self.hub_name: str = self.hub.name
        self.hub_id: str = self.hub.id
        self.hub_id_decoded: str = b64_url_safe_decode(self.hub_id)
        self.hub_team_name: str = self.hub_id_decoded.split(':')[-1]
        self.project_name: str = self.project.name
        self.project_id: str = self.project.id
        self.project_id_decoded: str = b64_url_safe_decode(self.project_id)
        self.folder_name: str = self.folder.name
        self.folder_id: str = self.folder.id
        self.lineage_urn: str = self.data_file.id
        self.version_urn: str = self.data_file.versionId
        self.base64_lineage_urn: str = b64_url_safe_encode(self.lineage_urn)
        self.base64_version_urn: str = b64_url_safe_encode(self.version_urn)

        team_base_url: str = 'autodesk360'
        self.open_from_web: str = f"fusion360://userEmail={self.user_email}&" \
                                  f"lineageUrn={self.lineage_urn}&" \
                                  f"hubUrl=https://{self.hub_team_name}.{team_base_url}.com&" \
                                  f"documentName={self.file_name}"
        self.fusion_team_url: str = f"https://{self.hub_team_name}.{team_base_url}.com/g/data/{self.base64_lineage_urn}"
        self.fusion_team_link = link_for_url(self.fusion_team_url)

    def str_dict(self):
        return {k: v
                for k, v in self.__dict__.items()
                if isinstance(v, str)}

    def pretty_string(self):
        return pprint.pformat(self.str_dict())

# @dataclass
# class ForgeFusionData(FusionData):
#     thumbnail_url: str = f"https://developer.api.autodesk.com/modelderivative/v2/designdata/" \
#                          f"{b64_lineage_urn}/thumbnail"