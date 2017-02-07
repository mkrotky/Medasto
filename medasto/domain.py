"""Collection of classes representing the Medasto model.

Classes in this module are returned from the getters in clientservice.ClientService.
There is usually no need to instantiate them directly. Most classes contain id fields
of their parents too. That is because many methods in ClientService expect not only
one id to identify an object but instead the complete hierarchy.

Most of the classes in here overwrite __str__(). The returned str always starts with
the class name followed by a colon. Then some important fields (but NOT all) follow.
This way a print(object) will help you better understand what the methods in ClientService
have returned from the server. That might be especially useful during the learning
phase of this api.

-------------------------------

Structure:

Please note that not all objects within the hierarchy are presented by custom classes.
If an object is simple (i.e. it contains only an id and name field) then the ClientService
returns this as a dictionary. Of course this is then documented on the corresponding
method. In the following tree the objects with a related custom class are
enclosed in single quotes. Their fields are documented in the class definition.

The tree as shown below does not exist in this api as one object. It it rather intended
to give you an overview how the Medasto Model is organized. If you want to build one
Project-object which contains all children down to the leaves then you have to build
this yourself. This is not recommended. First of all depending on your project(s)
the object structure might get very big and therefore memory consuming and 2nd as
server applications imply the model is a living object meaning it might constantly
change on the server side.

                                                                #method name

-Project (list)                                                 #get_project_list
    -id
    -name
    -AssetList (list)                                           #get_assetlist_list
        -id
        -name
        -'Status' (list)                                        #get_asset_statuslist
        -'JobDefinition' (list)                                 get_asset_jobdeflist
        -Asset (list)                                           #get_asset_list
            -'Job' (list)                                       #get_assetjob
                -see 'Job' class for substructure

    -ShotSection
        -'Status' (list, shared by all ShotLists)               #get_shot_statuslist
        -'JobDefinition' (list, shared by all ShotLists)        #get_shot_jobdeflist
        -TextContainers (list)                                  #get_textcontainers
            -textContainerId
            -labelName
            -maxCharCount
            -maxRowCount
        -TextPools (list)                                       #get_textpools
            -textPoolId
            -labelName
            -maxCharCount
            -textEntries (list of dicts)
                {entryId:text}
        -AssetTextPools (list)                                  #get_assettextpools
            -assetTextPoolId
            -labelName
            -maxCharCount
            -assetListId
        -'ShotList' (list)                                      #get_shotlist(s)
            -'Stage' (list)                                     #get_stage(s)
                -'Shot' (list)                                  #get_shots_from_shotlist
                                                                #get_shots_from_stage
                                                                #get_shot
                    -'Job' (list)                               #get_shotjob
                    -'StbSheet' (list)                          #get_stbsheet(s)




"""
__author__ = 'Michael Krotky'


class JobDefinition:
    """This class represents a preset that is used to create a Job for an Asset or Shot.

    JobDefinitions are set up for all 'ShotList's and for each AssetList. Each Asset or Shot
    that is added to such a list gets automatically one Job for each of the JobDefinitions
    in that list.

    -------------------------------------------------------------------------

    Fields:

    `jobdefid` (int)

    `name` (str) - on the GUI-Client this is the column name

    `headername` (str) - an optional heading which can visually group JobDefinitions
    together. On the GUI-Client this is displayed above the column names.

    `donestatusid` (int) - statusid indicating when the Job can be considered done. The GUI-Client
    uses this field in combination with `requiredtocomplete` to determine whether an asset or
    a shot is complete. This is true if all its Jobs that have `requiredtocomplete` set to true
    are done.

    `inclappendagesforjobstatus` (bool) - if True then the status of a Job is determined by the
    most recent jobentry which can be an 'Appendage' or a 'Message'. If false then only
    'Message' jobentries are considered.

    `initstatusid` (int) - as long as no 'Message' and 'Appendage' objects are present the
    'Job' will return this statusid

    `statusidsappendagemsg_list` (list<int>) - available statusids that can be used to add
    a 'Message' to an Appendage.

    `statusidsglobalmsg_list` (list<int>) - available statusids that can be used to add
    a 'Message' to the 'Job' directly. These messages are called GlobalMessage.

    `position` (int) - zero based position. This is the order the columns are displayed from
    left to right in the GUI-Client.

    `requiredtocomplete` (bool) - see `donestatusid`

    `color_r` (int) - red value 0 - 255. The color of the column name in the GUI-Client.
    `color_g` (int) - green value 0 - 255. The color of the column name in the GUI-Client.
    `color_b` (int) - blue value 0 - 255. The color of the column name in the GUI-Client.
    """
    def __init__(self, jobdefid, name, headername, donestatusid, inclappendagesforjobstatus, initstatusid,
                 statusidsappendagemsg_list, statusidsglobalmsg_list, position, requiredtocomplete,
                 color_r, color_g, color_b):

        self.jobdefid = jobdefid
        self.name = name
        self.headername = headername
        self.donestatusid = donestatusid
        self.inclappendagesforjobstatus = inclappendagesforjobstatus
        self.initstatusid = initstatusid
        self.statusidsappendagemsg_list = statusidsappendagemsg_list
        self.statusidsglobalmsg_list = statusidsglobalmsg_list
        self.position = position
        self.requiredtocomplete = requiredtocomplete
        self.color_r = color_r
        self.color_g = color_g
        self.color_b = color_b

    def __str__(self):
        return _tostring('JobDefinition',
                         'name', self.name,
                         'jobdefid', self.jobdefid,
                         'initstatusid', self.initstatusid,
                         'donestatusid', self.donestatusid,
                         'position', self.position,
                         'color', _color_to_str(self.color_r, self.color_g, self.color_b))


class Status:
    """Each 'Message' and 'Appendage' has a Status(id) associated.

    ALL Shots within a project share one Status-Pool. But each AssetList has its own
    Status-Pool. A Status indicates the current work progress of a 'Job'

    Fields:

    `statusid` (int)

    `fullname` (str) - for example "approved"

    `shortname` (str) - for example "appr"

    `color_r` (int) - red value 0 - 255. The color that is used for that Status in the GUI-Client.

    `color_g` (int) - red value 0 - 255. The color that is used for that Status in the GUI-Client.

    `color_b` (int) - red value 0 - 255. The color that is used for that Status in the GUI-Client.
    """
    def __init__(self, statusid, fullname, shortname, color_r, color_g, color_b):
        self.statusid = statusid
        self.fullname = fullname
        self.shortname = shortname
        self.color_r = color_r
        self.color_g = color_g
        self.color_b = color_b

    def __str__(self):
        return _tostring('Status',
                         'fullname', self.fullname,
                         'shortname', self.shortname,
                         'statusid', self.statusid,
                         'color', _color_to_str(self.color_r, self.color_g, self.color_b)
                         )


class Message:
    """Messages are used within 'Job's.

    If a Message is used directly as an entry within a 'Job' then it is called a "GlobalMessage".
    If a Message is part of an 'Appendage' then if is called an "AppendageMessage".
    A Message is used to set a 'Status' on an 'Appendage' or on a 'Job' directly. If no message
    text is required the `msgtext` field can be left empty.

    Fields:

    `msgid` (int)
    `datetime` (int) - ms since 1st Jan 1970.
    `statusid` (int) - see class definition 'Status'
    `msgtext` (str) - could be empty if the Message is only used to set a new Status.
    `author` (str) - The user who created the Message.
    """
    def __init__(self, msgid, msgdatetime, statusid, msgtext, author):
        self.msgid = msgid
        self.datetime = msgdatetime
        self.statusid = statusid
        self.msgtext = msgtext
        self.author = author

    def __str__(self):
        return _tostring('Message',
                         'msgid', self.msgid,
                         'datetime', self.datetime,
                         'statusid', self.statusid,
                         'author', self.author,
                         'msgtext', self.msgtext
                         )


class Appendage:
    """Appendages are used within 'Job's.

    An Appendage is a direct job entry like a GlobalMessage as well. It represents an
    uploaded file, folder or image sequence.

    Fields:

    `appendageid` (int)

    `filename` (str) - in case of an image sequence this is the base filename
    (without index)

    `isfrozen` (bool) - if true then the Appendage is not taken into consideration for
    the final Job's status calculation. The GUI-Client has also an option to hide them.

    `haspreviews` (bool) - if true then Medasto was able to create a preview video and
    thumbnail right after the upload. Once a preview has been set it cannot be changed
    or removed. It can be created either by uploading an original version
    (constants.FILEVERSION_ORIGINAL) or bei uploading a preview file separately.

    `appendagetype` (int) - See constants.APPENDAGETYPE_* for possible values.
    This field indicates whether the content of this Appendage is a single file, an
    image sequence or an arbitrary folder.

    `mediatype` (int) - See constants.MEDIATYPE_* for possible values.
    If the corresponding file has not been uploaded yet or if Medasto does not recognize
    the media format then this field will always hold MEDIATYPE_UNKNOWN. In that case
    `haspreviews` will be always false. Please not that since Medasto Version 2.x you
    can supply separate files for the preview. This field is always related to the
    preview version. So for example if your original upload is a still image but you
    supply a mp3 file for the preview (for whatever reason you might have) then this
    field will hold the constant constants.MEDIATYPE_AUDIO.

    `isonline` (bool) - This gets always set to True as soon as an upload is complete.
    If an Appendage gets set offline this filed will revert back to FALSE.

    `size` (int) - The value is initially 0 and gets set when the first upload is complete.
    If an Appendage is set offline this field will maintain its current value. In case of a
    single file this will be the size of that file. In case of an image sequence it
    presents the sum of all image files together.

    `msg_list` (list<Message>) - list with 'Message' objects. An Appendage hast always
    at least one 'Message'. So this list will never be empty.
    """
    def __init__(self, appendageid, filename, isfrozen, haspreviews, appendagetype, mediatype,
                 isonline, size, msg_list):

        self.appendageid = appendageid
        self.filename = filename
        self.isfrozen = isfrozen
        self.haspreviews = haspreviews
        self.appendagetype = appendagetype
        self.mediatype = mediatype
        self.isonline = isonline
        self.size = size
        self.msg_list = msg_list

    def get_newest_message(self):
        """Returns the most recent Message of this Appendage.

        This is the last item within the list. Appendages coming from the server have
        always at least one Message.
        """
        return self.msg_list[-1]

    def get_datetime(self):
        """Returns the datetime of the most recent Message of this Appendage.

        This is the last item within the list. Appendages coming from the server have
        always at least one Message.
        """
        return self.get_newest_message().datetime

    def get_status_id(self):
        """Returns the status of the most recent Message of this Appendage.

        Appendages coming from the server have always at least one Message.
        """
        return self.get_newest_message().statusid

    def __str__(self):
        return _tostring('Appendage',
                         'filename', self.filename,
                         'appendageid', self.appendageid,
                         'isfrozen', self.isfrozen,
                         'haspreviews', self.haspreviews,
                         'appendagetype', self.appendagetype,
                         'mediatype', self.mediatype,
                         'size', self.size,
                         'isonline', self.isonline
                         )


class Job:
    """A Job is a task assigned to an Asset or 'Shot'.

    In the GUI-Client each table cell in the AssetList-Views and ShotList-Views represents
    one Job. The rows are the Items (Shot or Asset) and the columns the Job names. Jobs
    get automatically created according to the 'JobDefinition' list of the corresponding
    AssetList or 'ShotList'. Please see the class definition of 'JobDefinition' for more
    information on that.

    A Job maintains its own list of job entries where such an entry is either a 'Message'
    or an 'Appendage'. A 'Message' located directly in a Job is called a "GlobalMessage".
    An 'Appendage' has its own 'Message' list. These messages are called
    "AppendageMessage". In most cases you don't have to access the `entry_list` of this
    class directly because convenient getters are supplied to access the individual
    elements of the Job's substructure.

    Fields:

    `jobid` (int)

    `jobdefinition` (complete 'JobDefinition' object)

    `entry_list` (list containing 'Message' and 'Appendage' instances). Several convenient
    getters are provided in order to access elements from this list.
    """
    def __init__(self, jobid, jobdefinition, entry_list):
        self.jobid = jobid
        self.jobdefinition = jobdefinition
        self.entry_list = entry_list

    def get_newest_jobentry(self, includefrozen):
        """Returns the newest job entry of this Job.

        This can be either of type 'Message' or 'Appendage'. If no entry exists
        then None is returned. If only frozen Appendages exist and includeFrozen
        is false, then None is returned as well.

        If includeFrozen is false, then frozen Appendages are ignored meaning the
        return value is either a GlobalMessage or an Appendage which is NOT frozen.
        """
        if includefrozen:
            if len(self.entry_list) > 0:
                return self.entry_list[-1]
        else:
            for jobentry in reversed(self.entry_list):
                if isinstance(jobentry, Appendage):
                    if jobentry.isfrozen():
                        continue  # ignore this frozen appendage
                return jobentry  # could be a GlobalMessage or an Appendage.
        return None

    def get_newest_appendage(self, includefrozen):
        """Returns the most recent 'Appendage' of this Job.

        If no Appendage exists then None is returned.
        If only frozen Appendages exist and includeFrozen is false, then None is
        returned as well.

        If includeFrozen is false, then frozen Appendages are ignored meaning if
        the return value is NOT None then it is certainly an Appendage which is
        NOT frozen.
        """
        for jobentry in reversed(self.entry_list):
            if isinstance(jobentry, Appendage):
                if (not includefrozen) and jobentry.isfrozen():
                    continue  # ignore this frozen appendage
                return jobentry
        return None

    def get_newest_message(self):
        """Returns the most recent GlobalMessage (instance of 'Message') of this Job.

        If no GlobalMessage exists then None is returned.
        """
        for jobentry in reversed(self.entry_list):
            if isinstance(jobentry, Message):
                return jobentry
        return None

    def get_appendage(self, appendageid):
        """Returns the 'Appendage' for the given appendageid

        None is returned if..
        a) no entry for the given appendageid exists or
        b) the entry exists but is not of type 'Appendage' (then it is a 'Message').
        """
        for jobentry in self.entry_list:
            if isinstance(jobentry, Appendage) and jobentry.appendageid == appendageid:
                return jobentry
        return None

    def get_appendage_list(self):
        """Returns a list with 'Appendage' instances.

        If no 'Appendage' exists then an empty list is returned (never None).
        """
        appendagelist = []
        for jobentry in self.entry_list:
            if isinstance(jobentry, Appendage):
                appendagelist.append(jobentry)
        return appendagelist

    def get_message(self, messageid):
        """Returns the 'Message' for the given messageid

        None is returned if..
        a) no entry for the given messageid exists or
        b) the entry exists but is not of type 'Message' (then it is an 'Appendage').
        """
        for jobentry in self.entry_list:
            if isinstance(jobentry, Message) and jobentry.messageid == messageid:
                return jobentry
        return None

    def get_message_list(self):
        """Returns a list with instances of type 'Message'.

        If no 'Message' exists then an empty list is returned (never None).
        """
        msglist = []
        for jobentry in self.entry_list:
            if isinstance(jobentry, Message):
                msglist.append(jobentry)
        return msglist

    def get_jobstatus_id(self):
        """Calculates and returns the statusId of this Job.

        If `jobdefinition`.inclappendagesforjobstatus is true then the statusid of the
        newest job entry ('Message' or 'Appendage') is returned. If there is no job entry
        then `jobdefinition`.initstatusid is returned (acting as default value).
        If `jobdefinition`.inclappendagesforjobstatus is false then the statusid
        of the newest GlobalMessage is returned. So Appendages are ignored. If there
        is no GlobalMessage then `jobdefinition`.initstatusid is returned.

        Frozen Appendages are always ignored for the status calculation.
        """
        if self.jobdefinition.inclappendagesforjobstatus:
            # so take Message- and Appendage-Entries into consideration..
            jobentry = self.get_newest_jobentry(False)  # job status is always calculated by ignoring frozen Appendages
            if jobentry is not None:
                return jobentry.get_status_id()
            else:
                return self.jobdefinition.initstatusid  # so no JobEntry at all and we fall back to the initStatus
        else:
            # so only take the Message entries into consideration..
            message = self.get_newest_message()
            if message is not None:
                return message.get_status_id()
            else:
                # so no global Messages exist and we fall back to the initStatus. Appendages might exist or not.
                return self.jobdefinition.initstatusid

    def is_done(self):
        """Returns true if this Job has reached its `jobdefinition`.donestatusid.

        This method call will calculate the job status and compare it
        with `jobdefinition`.donestatusid.
        """
        return self.get_jobstatus_id() == self.jobdefinition.donestatusid

    def __str__(self):
        return _tostring('Job',
                         'jobid', self.jobid,
                         'jobdefinition(id/name)', str(self.jobdefinition.jobdefid) + '/' + self.jobdefinition.name
                         )


class StbFields:
    """Abstract class. Not intended to be used directly.

    `textcontainers` - dict (keys:textcontainer_id, values: text)
    `textpools` - dict (keys:textpool_id, values: entry_id )
    `assettextpools` - dict (keys:assettextpool_id, values: asset_id)

    The getters in the ClientService for ShotList, Stage, Shot and StbSheet objects contain an
    `incl_stb_fields` parameter. When this is left False (default) the fields of this class
    will point to 'None' (instead to an empty dict).
    """
    def __init__(self, dct_tc, dct_tp, dct_atp):
        self.textcontainers = dct_tc
        self.textpools = dct_tp
        self.assettextpools = dct_atp


class AssetRelation:
    """Abstract class. Not intended to be used directly.

    `asset_relation` - dict (keys:assetlist_id, values: a set with asset_ids)

    For example if this class belongs to a Shot then all asset_ids within the dict are
    assigned to that Shot. All asset_ids are unique within a project. So they could be
    all in one set but this way it is easier to keep track to which assetlist they
    belong to.

    The getters in the ClientService for ShotList, Stage and Shot objects contain an
    `incl_asset_rel` parameter. When this is left False (default) the field of this class
    will point to 'None' (instead to an empty dict).
    """
    def __init__(self, asset_relation):
        self.asset_relation = asset_relation


class ShotList(StbFields, AssetRelation):
    """Parent of a 'Stage' and child of a project.

    Fields:
    `shotlist_id` (int)
    `shotlist_name` (str)
    `shotlist_shortname` (str)
    `shotlist_position` (int) zero based

    Inherited fields from class 'StbFields':
    `textcontainers`
    `textpools`
    `assettextpools`

    Inherited fields from class 'AssetRelation':
    `asset_relation`
    """
    def __init__(self, shotlist_id, shotlist_name, shotlist_shortname, shotlist_position,
                 dct_tc=None, dct_tp=None, dct_atp=None, asset_relation=None):
        self.shotlist_id = shotlist_id
        self.shotlist_name = shotlist_name
        self.shotlist_shortname = shotlist_shortname
        self.shotlist_position = shotlist_position
        StbFields.__init__(self, dct_tc, dct_tp, dct_atp)
        AssetRelation.__init__(self, asset_relation)

    def __str__(self):
        return _tostring('ShotList',
                         'shotlist_id', self.shotlist_id,
                         'shotlist_name', self.shotlist_name,
                         'shotlist_shortname', self.shotlist_shortname,
                         'shotlist_position', self.shotlist_position
                         )


class Stage(StbFields, AssetRelation):
    """Parent of a 'Shot' and child of a 'ShotList'.

    Fields:
    `shotlist_id` (int)
    `stage_id` (int)
    `custom_stage_id` (str)
    `stage_name` (str)
    `stage_position` (int) zero based

    Inherited fields from class 'StbFields':
    `textcontainers`
    `textpools`
    `assettextpools`

    Inherited fields from class 'AssetRelation':
    `asset_relation`
    """
    def __init__(self, shotlist_id, stage_id, custom_stage_id, stage_name, stage_position,
                 dct_tc=None, dct_tp=None, dct_atp=None, asset_relation=None):
        self.shotlist_id = shotlist_id
        self.stage_id = stage_id
        self.custom_stage_id = custom_stage_id
        self.stage_name = stage_name
        self.stage_position = stage_position
        StbFields.__init__(self, dct_tc, dct_tp, dct_atp)
        AssetRelation.__init__(self, asset_relation)

    def __str__(self):
        return _tostring('Stage',
                         'stage_id', self.stage_id,
                         'stage_name', self.stage_name,
                         'custom_stage_id', self.custom_stage_id,
                         'stage_position', self.stage_position,
                         'shotlist_id', self.shotlist_id
                         )


class Shot(StbFields, AssetRelation):
    """Parent of a 'StbSheet' and child of a 'Stage'.

    Fields:
    `shotlist_id` (int)
    `stage_id` (int)
    `custom_stage_id` (str)
    `shot_id` (int)
    `custom_shot_id` (str)
    `shot_name` (str)
    `shot_position` (int) zero based

    Inherited fields from class 'StbFields':
    `textcontainers`
    `textpools`
    `assettextpools`

    Inherited fields from class 'AssetRelation':
    `asset_relation`
    """
    def __init__(self, shotlist_id, stage_id, custom_stage_id, shot_id, custom_shot_id, shot_name, shot_position,
                 dct_tc=None, dct_tp=None, dct_atp=None, asset_relation=None):
        self.shotlist_id = shotlist_id
        self.stage_id = stage_id
        self.custom_stage_id = custom_stage_id
        self.shot_id = shot_id
        self.custom_shot_id = custom_shot_id
        self.shot_name = shot_name
        self.shot_position = shot_position
        StbFields.__init__(self, dct_tc, dct_tp, dct_atp)
        AssetRelation.__init__(self, asset_relation)

    def __str__(self):
        return _tostring('Shot',
                         'shot_id', self.shot_id,
                         'shot_name', self.shot_name,
                         'custom_shot_id', self.custom_shot_id,
                         'shot_position', self.shot_position,
                         'stage_id', self.stage_id,
                         'custom_stage_id', self.custom_stage_id,
                         'shotlist_id', self.shotlist_id
                         )


class StbSheet(StbFields):
    """Child element of a 'Shot'.

    Fields:
    `shotlist_id` (int)
    `stage_id` (int)
    `custom_stage_id` (str)
    `shot_id` (int)
    `custom_shot_id` (str)
    `stbsheet_id` (int)
    `stbimage_id` (int)
    `stbsheet_position` (int) zero based

    Inherited fields from class 'StbFields':
    `textcontainers`
    `textpools`
    `assettextpools`
    """
    def __init__(self, shotlist_id, stage_id, custom_stage_id, shot_id, custom_shot_id, stbsheet_id, stbimage_id,
                 stbsheet_position, dct_tc=None, dct_tp=None, dct_atp=None):
        self.shotlist_id = shotlist_id
        self.stage_id = stage_id
        self.custom_stage_id = custom_stage_id
        self.shot_id = shot_id
        self.custom_shot_id = custom_shot_id
        self.stbsheet_id = stbsheet_id
        self.stbimage_id = stbimage_id
        self.stbsheet_position = stbsheet_position
        StbFields.__init__(self, dct_tc, dct_tp, dct_atp)

    def __str__(self):
        return _tostring('StbSheet',
                         'stbsheet_id', self.stbsheet_id,
                         'stbimage_id', self.stbimage_id,
                         'stbsheet_position', self.stbsheet_position,
                         'shot_id', self.shot_id,
                         'custom_shot_id', self.custom_shot_id,
                         'stage_id', self.stage_id,
                         'custom_stage_id', self.custom_stage_id,
                         'shotlist_id', self.shotlist_id
                         )


def _tostring(clazzname, *args, pairsep='; ', namevaluesep='='):
    result = clazzname + ": "
    for i in range(0, len(args), 2):
        result = (result + args[i] + namevaluesep + str(args[i+1]))
        if i < len(args)-2:
            result += pairsep
    return result


def _color_to_str(r, g, b):
    return '(' + str(r) + ',' + str(g) + ',' + str(b) + ')'
