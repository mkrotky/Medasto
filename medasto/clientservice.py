"""Public module containing the 'ClientService' class.

Tested with Python 3.4.3
This module uses only features from the standard library. There are no external
dependencies.

******************************************************************************
****** PLEASE READ THIS INTRODUCTION COMPLETELY BEFORE USING THE MODULE *******
******************************************************************************


-------------------------- Conventions / Terms -------------------------------

If a class name (CamelCase) is enclosed in single quotes (') then it is
defined in the module Domain.py. There you can find additional documentation.

If the documentation refers to local variables or method parameters then the
attribute names are enclosed in (`).

It is assumed that the user of this API is familiar with the general concepts
and terms of the Medasto System.


-------------------------- Introduction / Quickstart -------------------------

The 'ClientService' class contains all available service methods for exchanging
data with the Medasto Server. In the simplest case the class can be instantiated
with customerId, username and password. Before you can then start using the
methods on the service object you first have to select a project:

    medservice = medasto.clientservice.ClientService("customerid", "user", "passw")
    projectlist = medservice..get_project_list()
    project_id = projectlist[0]['id']  # using 1st project in the list
    medservice.select_project(project_id)

Please note: At the time of creating an instance of 'ClientService' the machine
running the Python code needs a connection to the Medasto server. Once you have
obtained the instance the connection may drop without putting it in an
inconsistent state. Of course the service won't be available until the connection
is regained.


------------ Specifying Assets, Stages and Shots as method arguments ---------

In Medasto you identify an object within a hierarchy by giving the service methods
the id of the object in question plus the ids of the parent objects. For example
a Shot is identified with (shotlist_id, stage_id, shot_id). On first sight this
seems a little bit cumbersome but the service methods usually return objects
with all the ids from the parent objects. In the case of the shot this
means that the 'Shot' class also provides the ids for its 'Stage' and 'ShotList'
However there remains one problem left: All these ids (all Integers) are
created by Medasto and of course they are not related to objects in your
pipeline. If we're talking about a shot in Medasto with the name
"Ep01_Sc010_Sh0010", that shot might also exist in your pipeline and soon or
later we need to establish a relationship between them.
For Assets, Shots and Stages you can set a custom_id. This customId is
independent of the ids created by Medasto and you can use a String instead of a
number for them if you need to. It is your responsibility to provide unique ids
for each of these 3 item categories (though Medasto will throw an Exception
if you try to set a custom_id that is already occupied).

If you have set up custom_ids then you can choose on the corresponding methods
whether you want to provide the original ids from Medasto or just your custom_id.
That's why the method signatures are as follows:

doSomethingShot(shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None)
doSomethingStage(shotlist_id=None, stage_id=None, custom_stage_id=None)
doSomethingAsset(assetlist_id=None, asset_id=None, custom_asset_id=None)

If not stated otherwise you provide either the custom_id or the remaining ids
as shown above.


------------------------------- Session timeout ------------------------------

When an instance of 'ClientService' is created the provided credentials are sent
to the server and providing the credentials are valid a session is created. If
the server doesn't receive any request for a while then this session gets
invalidated. Further service method calls via the same 'ClientService' instance
will automatically..
    a) login again
    b) set the previous selected project (if any) in the newly created session.
    c) perform the original requested task (of the service method)
The service object will then continue to work with the new session. All this happens
transparently in the background. Of course this implies that the credentials are
kept in memory during the runtime of the script.


-------------------- Error handling / connection problems --------------------

We distinguish between 3 different Error categories:
    1)connection related: They get wrapped in a '_remoteservice.ConnectionMedEx'
    Exception.

    2)Medasto related: For example caused through invalid arguments/wrong ids
    ('ServerProcessingMedEx'), insufficient rights for the requested objects
    ('InsuffAuthMedEx'), wrong credentials('BadCredentialsMedEx'), etc.
    All these Exceptions happen on the server side and they will provide a
    message with the cause of the problem. If there is just an Error Code in
    the message then this could be an internal server error but doesn't have
    necessarily to be. In that case please double check the procedure that
    causes the Error and if it cannot be solved contact the Medasto support.

    3)everything else: For example in case of the upload and download service
    methods this might be an OSError during writing or reading a file. These
    Exceptions are thrown as they are.

Exceptions of 1) and 2) have the '_remoteservice.MedastoException' as the
Baseclass. So for the methods that don't deal with filesystem access it should
be enough to catch the 'MedastoException'.

When you create an instance of 'ClientService' you can overwrite two default
arguments: `waitaftererror` and 'maxtriesiferror'. They apply in case of
connection related Exceptions (see 1) above). If such errors occur the
script will wait `waitaftererror` seconds and then try it again. This is
repeated up to 'maxtriesiferror' before the last occurred Exception is
thrown. Exceptions of category 2) and 3) have in general no chance to recover.
So they are always thrown immediately.


-------------------------------- User rights ---------------------------------

The user is subject to the same rights management as any other user in Medasto
too. So please keep in mind to grant that user in the GUI-Client the necessary
rights. Otherwise the service method might not return all the data that you
expect. You must also assign that user to the service group "ROLESERVICE_API".
This can be accomplished in the "Manage Users/Groups"-section of the GUI-Client.

-------------------------------- Concurrency ---------------------------------

As long as you don't change the current project with .select_project(..) you
can access and use the 'ClientService' instance from several threads
concurrently. However if you have to switch to another project then you must
NOT access the instance concurrently. Method parameters refer always to
the current selected project. If you invoke .select_project(..) while other
threads are using some service methods of the same instance the server
might receive parameters for the wrong project!

If you need to work with several projects at the same time then you must create
a separate instance of 'ClientService' for each project. And because Medasto
allows only one session per user at the same time you will have to provide
a separate username for each of the instances as well.

"""
import json
import os
import os.path
import pathlib
from . import _remoteservice
from . import domain
from . import goodies

__author__ = 'Michael Krotky'

_FOLDER_UPLOAD_ALL_COMPLETE = -1
_IMAGESEQ_UPLOAD_COMPLETE = "IMAGESEQ**TRANSFER**COMPLETE"
_ERROR_MSG_ASSET_IDS = "You must either specify asset_list_id and asset_id together or the custom_asset_id"
_ERROR_MSG_SHOT_IDS = "You must either specify shot_list_id, stageId and shot_id together or the custom_shot_id"
_ERROR_MSG_STAGE_IDS = "You must either specify shot_list_id and stageId together or the custom_stage_id"


class ClientService:
    """Main class to interact with the Medasto server.

    See the doc of this module for more info.
    """

    def __init__(self, customerid, username, password, waitaftererror=10, maxtriesiferror=10):
        """Constructor.

        After creating this instance you must call .select_project().

        Parameters:
        `customerid` (str) - unique id of your Medasto account.

        `username` (str) - keep in mind that only one user can be logged in at
        the same time.

        `password` (str)

        `waitaftererror` (int) - see last paragraph of the section
        "Error handling / connection problems" in the doc string of this module.

        `maxtriesiferror` (int) - see last paragraph of the section
        "Error handling / connection problems" in the doc string of this module.
        """
        self._rmtservice = _remoteservice.RemoteService(
            customerid, username, password, waitaftererror, maxtriesiferror)

    def select_project(self, projectid):
        """You can get the available projects with .get_project_list()

        If this method returns without Exeptions then all future method
        invocations are related to this selected projectid.

        NEVER INVOKE THIS METHOD WHILE OTHER THREADS ARE USING THIS
        'ClientService' instance! See also the "Concurrency" section at the
        beginning of this file.
        """
        self._rmtservice.select_project(projectid)

    def get_project_list(self):
        """ list[ dict{'id': projectId(int), 'name': projectName(str)}, ..] """
        url = _url_from_args("project-list")
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_assetlist_list(self):
        """ list[ dict{'name': assetListName(str), 'id': assetListId(int)}, ..] """
        url = _url_from_args("assetListIC")
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_asset_list(self, asset_list_id=None):
        """ list[ dict{'name': 'assetName(str)', 'id': assetId(int),
            'customId': customId(str), 'assetListId': assetListId(int)}, ..]

        If `asset_list_id` is left None then the Assets from all AssetLists are
        returned. Otherwise only the Assets from the given `asset_list_id` are
        returned.
        If no 'customId' has been set then its value in the dict will be None.
        """
        if asset_list_id is None:
            url = _url_from_args("assetsICAll")
        else:
            url = _url_from_args("assetList", asset_list_id, "assetsIC")
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_asset_statuslist(self, asset_list_id):
        """Returns a list with 'Status' objects from the given `asset_list_id` """
        url = _url_from_args("assetList", asset_list_id, "statusList")
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_status)

    def get_asset_jobdeflist(self, asset_list_id):
        """Returns a list with 'JobDefinition' objects from the given `asset_list_id` """
        url = _url_from_args("assetList", asset_list_id, "jobDefList")
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_jobdef)

    def update_assetlist_addasset(self, asset_list_id, asset_name, custom_id=None):
        """Adds a new Asset to the given `asset_list_id`.

        The `custom_id` for the new Asset is optional.
        """
        url = _url_from_args("assetList", asset_list_id, "addAsset")
        jsondata = json.dumps(dict(customId=custom_id, name=asset_name))
        newid = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(newid)

    def update_assetlist_removeasset(self, asset_list_id=None, asset_id=None, custom_asset_id=None):
        """Deletes the specified Asset. """
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args("assetList", asset_list_id, "asset", asset_id, "delete")
            self._rmtservice.request(url, method='DELETE')
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "delete")
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def update_asset_customid(self, asset_list_id, asset_id, custom_id):
        """Updates or deletes the custom_id of the given Asset.

        The `custom_id` must not already exist within the "custom assetid pool". Otherwise
        an Exception is thrown. Use None for `custom_id` to remove it from the Asset.
        Custom_ids are always stored as Strings.
        """
        url = _url_from_args("assetList", asset_list_id, "asset", asset_id, "updateCustomId")
        jsondata = json.dumps(dict(customId=custom_id))
        self._rmtservice.request(url, method='POST', body=jsondata)

    def update_asset_name(self, assetname, asset_list_id=None, asset_id=None, custom_asset_id=None):
        """Updates the name of the given Asset.

        `assetname` (str)
        """
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args("assetList", asset_list_id, "asset", asset_id, "updateName")
            jsondata = json.dumps(dict(name=assetname))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "updateName")
            jsondata = json.dumps(dict(name=assetname, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        self._rmtservice.request(url, method='POST', body=jsondata)

    def get_assetjob(self, asset_list_id=None, asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Returns a 'Job' object (see doc string of 'Job').

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)

        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args(
                "assetList", asset_list_id, "asset", asset_id, "job", jobordef['id'], jobordef['isDefId'], "object")
            result_str = self._rmtservice.request(url)
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], "object")
            jsondata = json.dumps(dict(customId=custom_asset_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        return json.loads(result_str, object_hook=_objhook_job)

    def update_assetjob_addglobalmessage(self, msgtext, statusid, asset_list_id=None, asset_id=None,
                                         custom_asset_id=None, job_id=None, jobdef_id=None):
        """Adds a 'Message' to the Job.

        `msgtext` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool of the corresponding
        asset_list_id.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args(
                "assetList", asset_list_id, "asset", asset_id, "job", jobordef['id'], jobordef['isDefId'], "addMessage")
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], "addMessage")
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_assetjob_addappendagemessage(self, msgtext, statusid, appendage_id, asset_list_id=None, asset_id=None,
                                            custom_asset_id=None, job_id=None, jobdef_id=None):
        """Adds a 'Message' to the specified `appendage_id`.

        `msgtext` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool of the corresponding
        asset_list_id.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args(
                'assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                appendage_id, 'addMessage')
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "addMessage")
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_assetjob_addappendage(self, appendage_type, msgtext, statusid, filename, asset_list_id=None,
                                     asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Adds an 'Appendage' to the specified Job.

        This method does NOT upload any file data. It just adds a new entry to the
        specified 'Job'. The entry will be visible to all other users but the
        media will be marked offline until you upload the file with the method
        update_assetjob_uploadfile(..) or update_assetjob_uploadfolder(..).

        An 'Appendage' cannot exist without at least one 'Message'. The `msgtext`
        and `statusid` parameters will be used to create the 'Message'.

        `appendage_type` (int) - medasto.constants.APPENDAGETYPE_FILE or .APPENDAGETYPE_FOLDER.
        For Appendages that will contain an image sequence there is a separate add-method.

        `msgText` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool of the corresponding
        asset_list_id.

        `filename` (str) - just the name without the path.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        returns the appendage_id of the newly created 'Appendage' which you
        will need for the upload procedure.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'addAppendage')
            jsondata = json.dumps(
                dict(text=msgtext, statusId=statusid, fileName=filename, appendageType=appendage_type))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], "addAppendage")
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid, fileName=filename,
                                       customId=custom_asset_id, appendageType=appendage_type))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        result_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(result_str)

    def update_assetjob_addappendage_imageseq(self, msgtext, statusid, seqname, fps, asset_list_id=None,
                                              asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Adds an 'Appendage' to the specified Job.

        This method does NOT upload any image files. It just adds a new entry to the
        specified 'Job'. The entry will be visible to all other users but the
        media will be marked offline until you upload the image files with
        update_assetjob_init_imageseq_upload(..) and upload_imageseq_allfiles(..).

        An 'Appendage' cannot exist without at least one 'Message'. The `msgtext`
        and `statusid` parameters will be used to create the 'Message'.

        `msgText` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool of the corresponding
        asset_list_id.

        `seqname` (str) - The name that is displayed in the Job-Window of the
        Gui-Client. Usually the base image file name without the numbering and
        file extension ist used for that. But it can be any other string too as
        long as it conforms to a valid unix file name.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        returns the appendage_id of the newly created 'Appendage' which you
        will need for the upload procedure.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'addImageSeqAppendage')
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid, fileName=seqname, fps=fps))
        elif custom_asset_id is not None:
            url = _url_from_args(
                "assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], "addImageSeqAppendage")
            jsondata = json.dumps(
                dict(text=msgtext, statusId=statusid, fileName=seqname, fps=fps, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        result_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(result_str)

    def update_assetjob_uploadfile(self, appendage_id, filepath, create_preview, asset_list_id=None,
                                   asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' has been added.

        This method is used to upload a single file after a successful
        execution of update_assetjob_addappendage(..) with
        appendage_type=constants.APPENDAGETYPE_FILE.
        This method will fail if the 'Appendage' is currently online.

        The `filepath` for the file to be uploaded can be either a str or a byte-like
        object as expected by the native 'open' function of Python.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        extra_headers = {}
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'uploadSP', create_preview)
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "uploadSP", create_preview)
            extra_headers['customId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_assetjob_uploadfolder(self, folderpath, create_preview, appendage_id, asset_list_id=None, asset_id=None,
                                     custom_asset_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' has been added.

        This method is used to upload a folder (recursively) after a successful
        execution of update_assetjob_addappendage(..) with
        appendage_type=constants.APPENDAGETYPE_FOLDER.
        This method will fail if the 'Appendage' is currently online.

        If this method returns without raising an Exception the upload can be expected
        to be complete.

        The `folderpath` for the folder to be uploaded.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        pathlist_filedict = self._get_folder_structure(folderpath)
        pathlist = pathlist_filedict[0]  # relative paths to files and empty folders as expected by the server
        filedict = pathlist_filedict[1]  # key: file_id, value: absolute file paths

        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args(
                'assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                appendage_id, 'initFolderUpload', create_preview)
            jsondata = json.dumps(dict(pathlist=pathlist))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "initFolderUpload", create_preview)
            jsondata = json.dumps(dict(pathlist=pathlist, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        result_str = self._rmtservice.request(url, method='POST', body=jsondata)
        uploadjobid_nextfileid = json.loads(result_str)
        uploadjob_id = uploadjobid_nextfileid[0]
        nextfile_id = int(uploadjobid_nextfileid[1])

        #  A _FOLDER_UPLOAD_ALL_COMPLETE signal returned by the server guarantees that the upload is really complete..
        while nextfile_id != _FOLDER_UPLOAD_ALL_COMPLETE:
            if nextfile_id not in filedict:
                raise Exception("Server request an unknown file id: " + str(nextfile_id))
            absfilepath = filedict[nextfile_id]
            if not os.path.isfile(absfilepath):
                # This can onyl mean that the file has been deleted after the creation of the pathlist for the server.
                raise Exception(
                    "Given folder '" + folderpath + "' does not contain the requested file '" + absfilepath) + "'."
            url = _url_from_args("processAppendageFolderUpload", "uploadJob", uploadjob_id, 'file', nextfile_id)
            with open(absfilepath, 'rb') as file:
                nextfile_id = int(
                    self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream'))

    def update_assetjob_init_imageseq_upload(self, filenamelist, create_preview, appendage_id, asset_list_id=None,
                                             asset_id=None,
                                             custom_asset_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' for an image sequence has been added.

        This method is used to initialize the upload of an image sequence after a successful
        execution of update_assetjob_addappendage_imageseq(..).
        This method will fail if the 'Appendage' is currently online.

        `filenamelist` must point to a list containing all file names (str)
        that belong to the image sequence. The items in the list must be really
        just names and not paths.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        The method returns a unique uploadjob_id which is needed for the next
        and final upload step (method upload_imageseq_allfiles(..))
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args(
                'assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                appendage_id, 'initImageSeqUpload', create_preview)
            jsondata = json.dumps(dict(fileNameList=filenamelist))
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "initImageSeqUpload", create_preview)
            jsondata = json.dumps(dict(fileNameList=filenamelist, customId=custom_asset_id))
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        uploadjob_id = self._rmtservice.request(url, method='POST', body=jsondata)
        return uploadjob_id

    def upload_imageseq_onefile(self, uploadjob_id, filepath):
        """Upload a single image file for an image sequence.

        Please note: Usually this method is never needed to be used
        directly. It uploads a single image file that was registered
        with the invocation of update_assetjob_init_imageseq_upload(..) or
        update_shotjob_init_imageseq_upload(..). Consider using the more
        convenient upload_imageseq_allfiles(..) method which will handle
        the upload of all necessary files with just one method call.

        If for some reason you want to use this method then fetch the
        first file to be uploaded with the method upload_imageseq_getnext(..).

        Returns the next image file name to upload.
        """
        filename = os.path.basename(filepath)
        extra_headers = {'filename': filename}
        url = _url_from_args("processImageSeqUpload", "uploadJob", uploadjob_id)
        with open(filepath, 'rb') as file:
            nextitem = self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream',
                                                extra_headers=extra_headers)
        return nextitem

    def upload_imageseq_getnext(self, uploadjob_id):
        """Returns an arbitrary pending image file name of the given uploadjob_id.

        Please note: Usually this method is never needed to be used
        directly. Please see the doc string of the method
        upload_imageseq_onefile(..)
        """
        url = _url_from_args("processImageSeqUpload", "uploadJob", uploadjob_id, 'next')
        nextitem = self._rmtservice.request(url)
        return nextitem

    def upload_imageseq_allfiles(self, uploadjob_id, folderpath):
        """Uploads all files for the given uploadjob_id of an image sequence.

        The `uploadjob_id ` must belong to an upload job that was initialized
        via the method update_assetjob_init_imageseq_upload(..) or
        update_shotjob_init_imageseq_upload(..).

        'folderpath' must be a path object (str) that points to the folder
        containing the image files whose names were passed to the server in
        the previous mentioned init-upload methods. If the folder contains
        additional files or sub folders, then these are ignored. If the server
        requests an image file that is not contained in the given folder then
        an Exception is thrown.

        The server will feed the client with image files to be uploaded. As
        soon as the server has successfully received all image files this
        method will return and the server will set
        'Appendage' .isuploadcomplete and .isonline to true.

        This method can also be used to resume a previously cancelled (or crashed)
        upload as long as you have the uploadjob_id. In that case only the
        remaining files will be uploaded.
        """
        if not os.path.isdir(folderpath):
            raise Exception("Given path '" + folderpath + "' does not exist or is not a folder.")
        nextitem = self.upload_imageseq_getnext(uploadjob_id)
        while nextitem != _IMAGESEQ_UPLOAD_COMPLETE:
            filepath = os.path.join(folderpath, nextitem)
            if not os.path.isfile(filepath):
                raise Exception(
                    "Given folder '" + folderpath + "' does not contain the requested file '" + nextitem) + "'."
            nextitem = self.upload_imageseq_onefile(uploadjob_id, filepath)

    def _get_folder_structure(self, folderpath):
        """Returns a tuple ( pathlist, filedict ).

        pathlist contains dictionaries with relative paths from all files and empty directories within folderpath.
        filedict contains absolute paths to all files within the folder. The keys are unique file ids within folderpath.
        """
        if not os.path.isdir(folderpath):
            raise Exception("Given path '" + folderpath + "' does not exist or is not a folder.")

        pathlist = []
        filedict = {}
        fileid = 1  # server reqires to start counting at 1 or above.
        for root, dirs, files in os.walk(folderpath, topdown=True, onerror=self._walktree_error_handler):
            if len(dirs) == 0 and len(files) == 0:
                relpath = os.path.relpath(root, folderpath)
                elements = pathlib.PurePath(relpath).parts
                pathlist.append({'id': fileid, 'elements': elements, 'size': 0, 'isdir': True})
                fileid += 1
            else:
                for name in files:
                    abspath = os.path.join(root, name)
                    relpath = os.path.relpath(abspath, folderpath)
                    elements = pathlib.PurePath(relpath).parts
                    size = os.path.getsize(abspath)
                    pathlist.append({'id': fileid, 'elements': elements, 'size': size})
                    filedict[fileid] = abspath
                    fileid += 1
        return pathlist, filedict

    def _walktree_error_handler(self, ex):
        raise ex  # OSError with filename attribute

    def update_assetjob_uploadpreview(self, appendage_id, filepath, asset_list_id=None,
                                      asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """To be used for preview uploads after an 'Appendage' has been added.

        This method can be used to upload a single preview file. It will fail if the
        'Appendage' already has a preview. The preview file can be either a video, a
        still image or an audio file. It is completely independent of the original
        upload. If the supplied file is a compatible format Medasto will used it
        directly otherwise it will try to convert it and discard the file of this upload.

        The `filepath` for the file to be uploaded can be either a str or a byte-like
        object as expected by the native 'open' function of Python.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        extra_headers = {}
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'uplPrevSP')
        elif custom_asset_id is not None:
            url = _url_from_args("assetList", "asset_c", "job", jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "uplPrevSP")
            extra_headers['customId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_assetjob_freeze_appendage(self, freeze, appendage_id, asset_list_id=None, asset_id=None,
                                         custom_asset_id=None, job_id=None, jobdef_id=None):
        """Freezes or unfreezes the given `appendage_id`.

        `freeze` (bool) - True in order to freeze it. False to unfreeze it.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'freeze', freeze)
            self._rmtservice.request(url, method='PUT')
        elif custom_asset_id is not None:
            url = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, 'freeze', freeze)
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.request(url, method='PUT', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def update_assetjob_remove_appendage(self, appendage_id, asset_list_id=None, asset_id=None,
                                         custom_asset_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `appendage_id`.

        Be aware that this will also delete the associated media file on the server.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_asset_id is not None:
            url = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def update_assetjob_remove_appendagemsg(self, appendage_id, msg_id, asset_list_id=None, asset_id=None,
                                            custom_asset_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `msg_id` from the given `appendage_id`

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'message', msg_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_asset_id is not None:
            url = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, 'message', msg_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def update_assetjob_remove_globalmsg(self, msg_id, asset_list_id=None, asset_id=None,
                                         custom_asset_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `msg_id`(GlobalMessage) from the given 'Job'

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'message', msg_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_asset_id is not None:
            url = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'message', msg_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def assign_asset_to_shot(self, addordel, asset_list_id=None, asset_id=None, custom_asset_id=None,
                             shot_list_id=None, stage_id=None, shot_id=None, custom_shot_id=None):
        """Assigns the specified Asset to the specified 'Shot' or removes it.

        `addordel` (bool) - If True then the Asset is assigned to the 'Shot'
        otherwise it is removed.

        If the Asset is assigned to the 'Shot' and the parents of the 'Shot'
        ('Stage' and 'ShotList') don't have it already associated then the
        Asset will be assigned to them as well.
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        if shot_list_id is not None and stage_id is not None and shot_id is not None:
            dct['spId'] = shot_list_id
            dct['stageId'] = stage_id
            dct['shotId'] = shot_id
        elif custom_shot_id is not None:
            dct['customShotId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        jsondata = json.dumps(dct)
        method = 'PUT' if addordel else 'DELETE'
        self._rmtservice.request("shotList/stage/shot/assign", method=method, body=jsondata)

    def assign_asset_to_stage(self, addordel, asset_list_id=None, asset_id=None, custom_asset_id=None,
                              shot_list_id=None, stage_id=None, custom_stage_id=None):
        """Assigns the specified Asset to the specified 'Stage' or removes it.

        `addordel` (bool) - If True then the Asset is assigned to the 'Stage'
        otherwise it is removed.

        If the Asset is assigned to the 'Stage' and the parent of the 'Stage'
        ('ShotList') doesn't have it already associated then the
        Asset will be assigned to the parent as well.
        If the Asset is removed from the 'Stage' then it is also removed from
        all children ('Shot').
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        if shot_list_id is not None and stage_id is not None:
            dct['spId'] = shot_list_id
            dct['stageId'] = stage_id
        elif custom_stage_id is not None:
            dct['customStageId'] = custom_stage_id
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        jsondata = json.dumps(dct)
        method = 'PUT' if addordel else 'DELETE'
        self._rmtservice.request("shotList/stage/assign", method=method, body=jsondata)

    def assign_asset_to_shotlist(self, addordel, shot_list_id, asset_list_id=None, asset_id=None, custom_asset_id=None):
        """Assigns the specified Asset to the specified 'ShotList' or removes it.

        `addordel` (bool) - If True then the Asset is assigned to the 'ShotList'
        otherwise it is removed.

        If the Asset is removed from the 'ShotList' then it is also removed from
        all children ('Stage' and 'Shot').
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        jsondata = json.dumps(dct)
        method = 'PUT' if addordel else 'DELETE'
        url = _url_from_args('shotList', shot_list_id, 'assign')
        self._rmtservice.request(url, method=method, body=jsondata)

    # *********************************************** Shot Part *********************************************************

    def get_shot_statuslist(self):
        """Returns a list with 'Status' objects which are valid vor all 'ShotList's. """
        result_str = self._rmtservice.request('shotStatusList')
        return json.loads(result_str, object_hook=_objhook_status)

    def get_shot_jobdeflist(self):
        """Returns a list with 'JobDefinition' objects which are valid vor all 'ShotList's. """
        result_str = self._rmtservice.request('shotJobDefList')
        return json.loads(result_str, object_hook=_objhook_jobdef)

    def get_textcontainers(self, layer):
        """Returns a list with TextContainers(dictionaries).

        The dictionaries have the following keys:
        'textContainerId' --> (int)
        'labelName' --> (str)
        'maxCharCount' --> (int)
        'maxRowCount' --> (int)

        See the LAYER_* constants of this module for valid layer arguments.
        """
        url = _url_from_args("tcList", layer)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_textpools(self, layer):
        """Returns a list with TextPools(dictionaries).

        The dictionaries have the following keys:
        'textPoolId' --> (int)
        'labelName' --> (str)
        'maxCharCount' --> (int)
        'textEntries' --> list[ dict{'entryId': text(str)}, ..]

        The 'textEntries' cannot be edited with this API. Please use the
        GUI-Client for this.

        See the LAYER_* constants of this module for valid layer arguments.
        """
        url = _url_from_args("tpList", layer)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_assettextpools(self, layer):
        """Returns a list with AssetTextPools(dictionaries).

        The dictionaries have the following keys:
        'assetTextPoolId' --> (int)
        'labelName' --> (str)
        'maxCharCount' --> (int)
        'assetListId' --> (int)

        See the LAYER_* constants of this module for valid layer arguments.
        """
        url = _url_from_args('atpList', layer)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str)

    def get_shotlists(self, incl_stb_fields=False, incl_asset_rel=False):
        """Same as get_shotlist(..) but..

        .returns a list of all 'ShotList' objects as list in correct order."""
        url = _url_from_args('shotList', 'list', incl_stb_fields, incl_asset_rel)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_shotlist)

    def get_shotlist(self, shotlist_id, incl_stb_fields=False, incl_asset_rel=False):
        """Returns a 'ShotList' object for the given `shotlist_id`.

        `incl_stb_fields` (bool) - if False then the storyboard related fields
        in the returned object `textcontainers`, `textpools` and `assettextpools`
        will remain None (saving bandwidth if not needed).

        `incl_asset_rel` (bool) - if False then the field `asset_relation` of the
        returned object will remain None (saving bandwidth if not needed).
        """
        url = _url_from_args('shotList', shotlist_id, 'object', incl_stb_fields, incl_asset_rel)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_shotlist)

    def get_stages(self, shotlist_id, incl_stb_fields=False, incl_asset_rel=False):
        """Same as get_stage(..) but..

        ..returns all 'Stage' objects of the specified `shotlist_id` as list in correct order."""
        url = _url_from_args('shotList', shotlist_id, 'stage', 'list', incl_stb_fields, incl_asset_rel)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_stage)

    def get_stage(self, shotlist_id=None, stage_id=None, custom_stage_id=None,
                  incl_stb_fields=False, incl_asset_rel=False):
        """Returns a 'Stage' object for the specified Stage.

        `incl_stb_fields` (bool) - please see get_shotlist(..)
        `incl_asset_rel` (bool) - please see get_shotlist(..)
        """
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'object', incl_stb_fields, incl_asset_rel)
            result_str = self._rmtservice.request(url)
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'object', incl_stb_fields, incl_asset_rel)
            jsondata = json.dumps(dict(customId=custom_stage_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        return json.loads(result_str, object_hook=_objhook_stage)

    def get_shots_from_shotlist(self, shotlist_id, incl_stb_fields=False, incl_asset_rel=False):
        """Same as get_shot(..) but..

         ..returns all 'Shot' objects of the specified `shotlist_id` as list in correct order.
         """
        url = _url_from_args('shotList', shotlist_id, 'shots', incl_stb_fields, incl_asset_rel)
        result_str = self._rmtservice.request(url)
        return json.loads(result_str, object_hook=_objhook_shot)

    def get_shots_from_stage(self, shotlist_id=None, stage_id=None, custom_stage_id=None,
                             incl_stb_fields=False, incl_asset_rel=False):
        """Same as get_shot(..) but..

        ..returns all 'Shot' objects of the specified Stage as list in correct order.
        """
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', 'list', incl_stb_fields, incl_asset_rel)
            result_str = self._rmtservice.request(url)
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'shot', 'list', incl_stb_fields, incl_asset_rel)
            jsondata = json.dumps(dict(customId=custom_stage_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        return json.loads(result_str, object_hook=_objhook_shot)

    def get_shot(self, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None,
                 incl_stb_fields=False, incl_asset_rel=False):
        """Returns a 'Shot' object for the specified Shot.

        `incl_stb_fields` (bool) - please see get_shotlist(..)
        `incl_asset_rel` (bool) - please see get_shotlist(..)
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'object', incl_stb_fields, incl_asset_rel)
            result_str = self._rmtservice.request(url)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'object', incl_stb_fields, incl_asset_rel)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        return json.loads(result_str, object_hook=_objhook_shot)

    def get_stbsheets(self, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None, incl_stb_fields=False):
        """Same as get_stbsheet(..) but..

        ..returns all 'StbSheet' objects of the specified Shot as list in correct order.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', 'list', incl_stb_fields)
            result_str = self._rmtservice.request(url)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stb', 'list', incl_stb_fields)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        return json.loads(result_str, object_hook=_objhook_stbsheet)

    def get_stbsheet(self, stbsheet_id, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None,
                     incl_stb_fields=False):
        """Returns a 'StbSheet' object for the specified stbsheet_id.

        `stbsheet_id` - not to be mixed up with the stbimage_id
        `incl_stb_fields` (bool) - please see get_shotlist(..)
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', stbsheet_id,
                                 'object', incl_stb_fields)
            result_str = self._rmtservice.request(url)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stb', stbsheet_id, 'object', incl_stb_fields)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        return json.loads(result_str, object_hook=_objhook_stbsheet)

    def get_shotjob(self, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None,
                    job_id=None, jobdef_id=None):
        """Returns a 'Job' object (see doc string of 'Job').

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'object')
            result_str = self._rmtservice.request(url)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'object')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            result_str = self._rmtservice.request(url, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        return json.loads(result_str, object_hook=_objhook_job)

    def update_shotjob_addglobalmessage(self, msgtext, statusid, shotlist_id=None, stage_id=None, shot_id=None,
                                        custom_shot_id=None, job_id=None, jobdef_id=None):
        """Adds a 'Message' to the Job.

        `msgtext` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool for shots.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'addMessage')
            jsondata = json.dumps(dict(customId=custom_shot_id, statusId=statusid, text=msgtext))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'addMessage')
            jsondata = json.dumps(dict(customId=custom_shot_id, statusId=statusid, text=msgtext))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shotjob_addappendagemessage(self, msgtext, statusid, appendage_id, shotlist_id=None, stage_id=None,
                                           shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Adds a 'Message' to the specified `appendage_id`.

        `msgtext` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool for shots.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'addMessage')
            jsondata = json.dumps(dict(customId=custom_shot_id, statusId=statusid, text=msgtext))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'addMessage')
            jsondata = json.dumps(dict(customId=custom_shot_id, statusId=statusid, text=msgtext))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shotjob_addappendage(self, appendage_type, msgtext, statusid, filename, shotlist_id=None, stage_id=None,
                                    shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Adds an 'Appendage' to the specified 'Job'.

        This method does NOT upload any file data. It just adds a new entry to the
        specified 'Job'. The entry will be visible to all other users but the
        media will be marked offline until you upload the file with the method
        update_shotjob_uploadfile(..) or update_shotjob_uploadfolder(..).

        An 'Appendage' cannot exist without at least one 'Message'. The `msgtext`
        and `statusid` parameters will be used to create the 'Message'.

        `appendage_type` (int) - medasto.constants.APPENDAGETYPE_FILE or .APPENDAGETYPE_FOLDER.
        For Appendages that will contain an image sequence there is a separate add-method.

        `msgText` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool of for shots.

        `filename` (str) - just the name without the path.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        returns the appendage_id of the newly created 'Appendage' which you
        will need for the upload procedure.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'addAppendage')
            jsondata = json.dumps(dict(statusId=statusid, text=msgtext,
                                       fileName=filename, appendageType=appendage_type))
        elif custom_shot_id is not None:
            url = _url_from_args(
                'shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'addAppendage')
            jsondata = json.dumps(dict(customId=custom_shot_id, statusId=statusid, text=msgtext,
                                       fileName=filename, appendageType=appendage_type))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        result_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(result_str)

    def update_shotjob_addappendage_imageseq(self, msgtext, statusid, seqname, fps, shotlist_id=None, stage_id=None,
                                             shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Adds an 'Appendage' to the specified 'Job'.

        This method does NOT upload any image files. It just adds a new entry to the
        specified 'Job'. The entry will be visible to all other users but the
        media will be marked offline until you upload the image files with
        update_shotjob_init_imageseq_upload(..) and upload_imageseq_allfiles(..).

        An 'Appendage' cannot exist without at least one 'Message'. The `msgtext`
        and `statusid` parameters will be used to create the 'Message'.

        `msgText` (str) - must not be None but can be an empty string.

        `statusid` (int) - must exist in the status pool for shots.

        `seqname` (str) - The name that is displayed in the Job-Window of the
        Gui-Client. Usually the base image file name without the numbering and
        file extension ist used for that. But it can be any other string too as
        long as it conforms to a valid unix file name.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        returns the appendage_id of the newly created 'Appendage' which you
        will need for the upload procedure.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'addImageSeqAppendage')
            jsondata = json.dumps(dict(text=msgtext, statusId=statusid, fileName=seqname, fps=fps))
        elif custom_shot_id is not None:
            url = _url_from_args(
                'shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'addImageSeqAppendage')
            jsondata = json.dumps(
                dict(text=msgtext, statusId=statusid, fileName=seqname, fps=fps, customId=custom_shot_id))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        result_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(result_str)

    def update_shotjob_uploadfile(self, appendage_id, filepath, create_preview, shotlist_id=None, stage_id=None,
                                  shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' has been added.

        This method is used to upload a single file after a successful
        execution of update_shotjob_addappendage(..) with
        appendage_type=constants.APPENDAGETYPE_FILE.
        This method will fail if the 'Appendage' is currently online.

        The `filepath` for the file to be uploaded can be either a str or a byte-like
        object as expected by the native 'open' function of Python.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        extra_headers = {}
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'uploadSP', create_preview)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "uploadSP", create_preview)
            extra_headers['customId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_shotjob_uploadfolder(self, folderpath, create_preview, appendage_id, shotlist_id=None, stage_id=None,
                                    shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' has been added.

        This method is used to upload a folder (recursively) after a successful
        execution of update_shotjob_addappendage(..) with
        appendage_type=constants.APPENDAGETYPE_FOLDER.
        This method will fail if the 'Appendage' is currently online.

        If this method returns without raising an Exception the upload can be expected
        to be complete.

        The `folderpath` for the folder to be uploaded.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        pathlist_filedict = self._get_folder_structure(folderpath)
        pathlist = pathlist_filedict[0]  # relative paths to files and empty folders as expected by the server
        filedict = pathlist_filedict[1]  # key: file_id, value: absolute file paths

        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'initFolderUpload', create_preview)
            jsondata = json.dumps(dict(pathlist=pathlist))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, 'initFolderUpload', create_preview)
            jsondata = json.dumps(dict(pathlist=pathlist, customId=custom_shot_id))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        result_str = self._rmtservice.request(url, method='POST', body=jsondata)
        uploadjobid_nextfileid = json.loads(result_str)
        uploadjob_id = uploadjobid_nextfileid[0]
        nextfile_id = int(uploadjobid_nextfileid[1])

        #  A _FOLDER_UPLOAD_ALL_COMPLETE signal returned by the server guarantees that the upload is really complete..
        while nextfile_id != _FOLDER_UPLOAD_ALL_COMPLETE:
            if nextfile_id not in filedict:
                raise Exception("Server request an unknown file id: " + str(nextfile_id))
            absfilepath = filedict[nextfile_id]
            if not os.path.isfile(absfilepath):
                # This can onyl mean that the file has been deleted after the creation of the pathlist for the server.
                raise Exception(
                    "Given folder '" + folderpath + "' does not contain the requested file '" + absfilepath) + "'."
            url = _url_from_args("processAppendageFolderUpload", "uploadJob", uploadjob_id, 'file', nextfile_id)
            with open(absfilepath, 'rb') as file:
                nextfile_id = int(self._rmtservice.request(
                    url, method='POST', body=file, contenttype='application/octet-stream'))

    def update_shotjob_init_imageseq_upload(self, filenamelist, create_preview, appendage_id, shotlist_id=None,
                                            stage_id=None,
                                            shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """To be used for uploads after an 'Appendage' for an image sequence has been added.

        This method is used to initialize the upload of an image sequence after a successful
        execution of update_shotjob_addappendage_imageseq(..).
        This method will fail if the 'Appendage' is currently online.

        `filenamelist` must point to a list containing all file names (str)
        that belong to the image sequence. The items in the list must be really
        just names and not paths.

        `create_preview` (bool) - Use TRUE if Medasto shall try to create a preview from the upload.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        The method returns a unique uploadjob_id which is needed for the next
        and final upload step (method upload_imageseq_allfiles(..))
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'initImageSeqUpload', create_preview)
            jsondata = json.dumps(dict(fileNameList=filenamelist))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "initImageSeqUpload", create_preview)
            jsondata = json.dumps(dict(fileNameList=filenamelist, customId=custom_shot_id))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        uploadjob_id = self._rmtservice.request(url, method='POST', body=jsondata)
        return uploadjob_id

    def update_shotjob_uploadpreview(self, appendage_id, filepath, shotlist_id=None, stage_id=None,
                                     shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """To be used for preview uploads after an 'Appendage' has been added.

        This method can be used to upload a single preview file. It will fail if the
        'Appendage' already has a preview. The preview file can be either a video, a
        still image or an audio file. It is completely independent of the original
        upload. If the supplied file is a compatible format Medasto will used it
        directly otherwise it will try to convert it and discard the file of this upload.

        The `filepath` for the file to be uploaded can be either a str or a byte-like
        object as expected by the native 'open' function of Python.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        extra_headers = {}
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'uplPrevSP')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'], 'appendage',
                                 appendage_id, "uplPrevSP")
            extra_headers['customId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='POST', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_shotjob_freeze_appendage(self, freeze, appendage_id, shotlist_id=None, stage_id=None,
                                        shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Freezes or unfreezes the given `appendage_id`.

        `freeze` (bool) - True in order to freeze it. False to unfreeze it.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'freeze', freeze)
            self._rmtservice.request(url, method='PUT')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'freeze', freeze)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='PUT', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_shotjob_remove_appendagemsg(self, appendage_id, message_id, shotlist_id=None, stage_id=None,
                                           shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `message_id` from the given `appendage_id`

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'message', message_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'message', message_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_shotjob_remove_appendage(self, appendage_id, shotlist_id=None, stage_id=None,
                                        shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `appendage_id`.

        Be aware that this will also delete the associated media file on the server.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                 jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_shotjob_remove_globalmessage(self, message_id, shotlist_id=None, stage_id=None,
                                            shot_id=None, custom_shot_id=None, job_id=None, jobdef_id=None):
        """Deletes the given `message_id`(GlobalMessage) from the given 'Job'

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'message', message_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'message', message_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_stbsheet_setimage(self, stbsheet_id, filepath, shotlist_id=None, stage_id=None,
                                 shot_id=None, custom_shot_id=None):
        """Replaces the image on the specified 'StbSheet'.

        The `filepath` for the image file to be uploaded. Can be either a str or a
        byte-like object as expected by the native 'open' function of Python.

        Please note that the given file is not saved on the server as is but instead
        a converted JPG-image (with probably a lower resolution) will be saved.

        If this method returns without Exception then the given file was successfully
        upload, converted and the converted image was set on the 'StbSheet'.
        """
        filename = os.path.basename(filepath)
        extra_headers = {'filename': filename}
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', stbsheet_id, 'new-image')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stb', stbsheet_id, 'new-image')
            extra_headers['customId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='PUT', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_stbsheet_textcontainer(self, stbsheet_id, textcontainer_id, text, shotlist_id=None, stage_id=None,
                                      shot_id=None, custom_shot_id=None):
        """Updates the text of the specified `textcontainer_id`.

        This method will set the given `text` on the specified `textcontainer_id`
        located in the given `stbsheet_id` ('StbSheet'). The `textcontainer_id`
        can be received by using the method get_textcontainers(..).
        Use None for the `text` value in order to clear the textcontainer.

        Please note that this method will throw an Exception if the given text
        does not fit into the configured width and height of the textcontainer.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', stbsheet_id,
                                 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(text=text))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stb', stbsheet_id, 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(customId=custom_shot_id, text=text))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_stbsheet_textpool(self, stbsheet_id, textpool_id, entry_id, shotlist_id=None, stage_id=None,
                                 shot_id=None, custom_shot_id=None):
        """Updates the text entry of the specified `textpool_id`.

        This method will set the given `entry_id` on the specified `textpool_id`
        located in the given `stbsheet_id` ('StbSheet'). The `textpool_id`
        and its available text entries can be received by using the
        method get_textpools(..).
        On the GUI-Client a TextPool is displayed as a drop-down menu where the
        text entries are the available options to select from.

        In order to clear a selected entry without setting a new one use
        constants.EMPTYVALUE for the `entry_id`.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', stbsheet_id,
                                 'tp', textpool_id, 'update', entry_id)
            self._rmtservice.request(url, method='PUT')
        elif custom_shot_id is not None:
            url = _url_from_args(
                'shotList', 'stage', 'shot_c', 'stb', stbsheet_id, 'tp', textpool_id, 'update', entry_id)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='PUT', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_stbsheet_assettextpool(self, stbsheet_id, pool_id,
                                      asset_list_id=None, asset_id=None, custom_asset_id=None,
                                      shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None):
        """Sets the specified Asset on the specified `pool_id`.

        This method will set the specified Asset on the specified `pool_id`
        located in the given `stbsheet_id` ('StbSheet'). The `pool_id`
        can be received by using the method get_assettextpools(..).
        On the GUI-Client an AssetTextPool is displayed as a drop-down menu.
        It always belongs to an AssetList and the Assets of that AssetList
        are the available options to select from. The connected AssetList
        for the AssetTextPool can also be received from the method
        get_assettextpools(..). If an Asset is specified that does not
        belong to the connected AssetList of this AssetTextPool then an
        Exception is thrown.

        In order to set no selected Asset for this AssetTextPool use
        constants.EMPTYVALUE as value for `asset_id`. In that case you
        must still specify the `asset_list_id` and you cannot use the
        `custom_asset_id`.
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            dct['spId'] = shotlist_id
            dct['stageId'] = stage_id
            dct['shotId'] = shot_id
        elif custom_shot_id is not None:
            dct['customShotId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        url = _url_from_args('shotList/stage/shot/stb', stbsheet_id, 'atp', pool_id, 'update')
        jsondata = json.dumps(dct)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shot_addstbsheet(self, filepath, position, shotlist_id=None, stage_id=None,
                                shot_id=None, custom_shot_id=None):
        """Inserts a new 'StbSheet' to he specified 'Shot'.

        The `position` is a zero based int. As with indexes of lists it must be
        >= 0 and <= shot.stbSheetList.size. The method get_stbsheets(..)
        delivers the complete list and the 'StbSheet' objects have a position
        field which might be helpful here.

        The `filepath` for the image file to be uploaded can be either a str or a
        byte-like object as expected by the native 'open' function of Python.

        Please note that the given file is NOT saved on the server as is but instead
        a converted JPG-image (with probably a lower resolution) will be saved.

        If this method returns without Exception then the given file was successfully
        upload, converted and the converted image was used to create new 'StbSheet'.
        This 'StbSheet' was then added to the 'Shot'.
        """
        filename = os.path.basename(filepath)
        extra_headers = {'filename': filename}
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'addStb', position)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'addStb', position)
            extra_headers['customId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        with open(filepath, 'rb') as file:
            self._rmtservice.request(url, method='PUT', body=file, contenttype='application/octet-stream',
                                     extra_headers=extra_headers)

    def update_shot_remove_stbsheet(self, stbsheet_id, shotlist_id=None, stage_id=None,
                                    shot_id=None, custom_shot_id=None):
        """Deletes the specified 'StbSheet'.

        This will also delete the corresponding image file of the 'StbSheet'.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stb', stbsheet_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stb', stbsheet_id, 'delete')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_shot_customid(self, shotlist_id, stage_id, shot_id, custom_shot_id):
        """Updates the custom_id of the specified 'Shot'.

        `custom_shot_id` (str) - must not already be associated with another
        'Shot' within the project. An existing value will be overwritten. None
        can be used to clear the custom_id.
        """
        url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'updateCustomId')
        jsondata = json.dumps(dict(customId=custom_shot_id))
        self._rmtservice.request(url, method='POST', body=jsondata)

    def update_shot_name(self, shotname, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None):
        """Updates the name of the specified 'Shot'."""
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'updateName')
            jsondata = json.dumps(dict(name=shotname))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'updateName')
            jsondata = json.dumps(dict(customId=custom_shot_id, name=shotname))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        self._rmtservice.request(url, method='POST', body=jsondata)

    def update_shot_textcontainer(self, textcontainer_id, text, shotlist_id=None, stage_id=None,
                                  shot_id=None, custom_shot_id=None):
        """Updates the text of the specified `textcontainer_id`.

        This method will set the given `text` on the specified `textcontainer_id`
        located in the given 'Shot'. The `textcontainer_id` can be received
        by using the method get_textcontainers(..).
        Use None for the `text` value in order to clear the textcontainer.

        Please note that this method will throw an Exception if the given text
        does not fit into the configured width and height of the textcontainer.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(text=text))
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(customId=custom_shot_id, text=text))
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shot_textpool(self, textpool_id, entry_id, shotlist_id=None, stage_id=None,
                             shot_id=None, custom_shot_id=None):
        """Updates the text entry of the specified `textpool_id`.

        This method will set the given `entry_id` on the specified `textpool_id`
        located in the given 'Shot'. The `textpool_id` and its available text
        entries can be received by using the method get_textpools(..).
        On the GUI-Client a TextPool is displayed as a drop-down menu where the
        text entries are the available options to select from.

        In order to clear a selected entry without setting a new one use
        constants.EMPTYVALUE for the `entry_id`.
        """
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'tp', textpool_id, 'update', entry_id)
            self._rmtservice.request(url, method='PUT')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'tp', textpool_id, 'update', entry_id)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='PUT', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_shot_assettextpool(self, pool_id, asset_list_id=None, asset_id=None, custom_asset_id=None,
                                  shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None):
        """Sets the specified Asset on the specified `pool_id`.

        This method will set the specified Asset on the specified `pool_id`
        located in the given 'Shot'. The `pool_id` can be received by using
        the method get_assettextpools(..).
        On the GUI-Client an AssetTextPool is displayed as a drop-down menu.
        It always belongs to an AssetList and the Assets of that AssetList
        are the available options to select from. The connected AssetList
        for the AssetTextPool can also be received from the method
        get_assettextpools(..). If an Asset is specified that does not
        belong to the connected AssetList of this AssetTextPool then an
        Exception is thrown.

        In order to set no selected Asset for this AssetTextPool use
        constants.EMPTYVALUE as value for `asset_id`. In that case you
        must still specify the `asset_list_id` and you cannot use the
        `custom_asset_id`.
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            dct['spId'] = shotlist_id
            dct['stageId'] = stage_id
            dct['shotId'] = shot_id
        elif custom_shot_id is not None:
            dct['customShotId'] = custom_shot_id
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

        url = _url_from_args('shotList/stage/shot/atp', pool_id, 'update')
        jsondata = json.dumps(dct)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_stage_addshot(self, shotname, position, custom_shot_id=None,
                             shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Inserts a new 'Shot' into he specified 'Stage'.

        `custom_shot_id`:
        The doc string at the beginning of this module explains the concept of
        identifying Shots and Stages with method parameters. This method
        requires to identify a 'Stage'. So you have the option to supply either
        `shotlist_id` and `stage_id` together or just the `custom_stage_id`.
        The presence of the `custom_shot_id` parameter might be confusing but
        it is for the new 'Shot' that will be created. And since using custom_ids
        is optional there is the default value None specified.

        The `position` is a zero based int. As with indexes of lists it must be
        >= 0 and <= stage.shotList.size. The method get_shots_from_stage(..)
        delivers the complete list and the 'Shot' objects have a position
        field which might be helpful here. Medasto allows to control see rights
        for each 'Shot'/user. If the ClientService was instantiated with a
        non-admin user then it is recommended to orient on the position properties
        because these values always reflect the true position on the server.

        `shotname` (str)

        returns the shot_id (int) of the newly created 'Shot'.
        """
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'addShot')
            jsondata = json.dumps(dict(name=shotname, customShotId=custom_shot_id, position=position))
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'addShot')
            jsondata = json.dumps(
                dict(customId=custom_stage_id, name=shotname, customShotId=custom_shot_id, position=position))
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        shotid_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(shotid_str)

    def update_stage_remove_shot(self, shotlist_id=None, stage_id=None, shot_id=None, custom_shot_id=None):
        """Deletes the specified 'Shot' including all its children and associated media files."""
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'delete')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def update_stage_customid(self, shotlist_id, stage_id, custom_stage_id):
        """Updates the custom_id of the specified 'Stage'.

        `custom_stage_id` (str) - must not already be associated with another
        'Stage' within the project. An existing value will be overwritten. None
        can be used to clear the custom_id.
        """
        url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'updateCustomId')
        jsondata = json.dumps(dict(customId=custom_stage_id))
        self._rmtservice.request(url, method='POST', body=jsondata)

    def update_stage_name(self, stagename, shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Updates the name of the specified 'Stage'."""
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'updateName')
            jsondata = json.dumps(dict(name=stagename))
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'updateName')
            jsondata = json.dumps(dict(customId=custom_stage_id, name=stagename))
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        self._rmtservice.request(url, method='POST', body=jsondata)

    def update_stage_textcontainer(self, textcontainer_id, text, shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Updates the text of the specified `textcontainer_id`.

        This method will set the given `text` on the specified `textcontainer_id`
        located in the given 'Stage'. The `textcontainer_id` can be received
        by using the method get_textcontainers(..).
        Use None for the `text` value in order to clear the textcontainer.

        Please note that this method will throw an Exception if the given text
        does not fit into the configured width and height of the textcontainer.
        """
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(text=text))
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'tc', textcontainer_id, 'update')
            jsondata = json.dumps(dict(customId=custom_stage_id, text=text))
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_stage_textpool(self, textpool_id, entry_id, shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Updates the text entry of the specified `textpool_id`.

        This method will set the given `entry_id` on the specified `textpool_id`
        located in the given 'Stage'. The `textpool_id` and its available text
        entries can be received by using the method get_textpools(..).
        On the GUI-Client a TextPool is displayed as a drop-down menu where the
        text entries are the available options to select from.

        In order to clear a selected entry without setting a new one use
        constants.EMPTYVALUE for the `entry_id`.
        """
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'tp', textpool_id, 'update', entry_id)
            self._rmtservice.request(url, method='PUT')
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'tp', textpool_id, 'update', entry_id)
            jsondata = json.dumps(dict(customId=custom_stage_id))
            self._rmtservice.request(url, method='PUT', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)

    def update_stage_assettextpool(self, pool_id, asset_list_id=None, asset_id=None, custom_asset_id=None,
                                   shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Sets the specified Asset on the specified `pool_id`.

        This method will set the specified Asset on the specified `pool_id`
        located in the given 'Stage'. The `pool_id` can be received by using
        the method get_assettextpools(..).
        On the GUI-Client an AssetTextPool is displayed as a drop-down menu.
        It always belongs to an AssetList and the Assets of that AssetList
        are the available options to select from. The connected AssetList
        for the AssetTextPool can also be received from the method
        get_assettextpools(..). If an Asset is specified that does not
        belong to the connected AssetList of this AssetTextPool then an
        Exception is thrown.

        In order to set no selected Asset for this AssetTextPool use
        constants.EMPTYVALUE as value for `asset_id`. In that case you
        must still specify the `asset_list_id` and you cannot use the
        `custom_asset_id`.
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        if shotlist_id is not None and stage_id is not None:
            dct['spId'] = shotlist_id
            dct['stageId'] = stage_id
        elif custom_stage_id is not None:
            dct['customStageId'] = custom_stage_id
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)

        url = _url_from_args('shotList/stage/atp', pool_id, 'update')
        jsondata = json.dumps(dct)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shotlist_addstage(self, shotlist_id, stagename, position, custom_stage_id=None):
        """Inserts a new 'Stage' into he specified 'ShotList'.

        `custom_stage_id`:
        The `custom_stage_id` parameter is for the new 'Stage' that will be
        created. And since using custom_ids is optional there is the default
        value None specified.

        The `position` is a zero based int. As with indexes of lists it must be
        >= 0 and <= shotList.stageList.size. The method get_stages(..)
        delivers the complete list and the 'Stage' objects have a position
        field which might be helpful here.

        `stagename` (str)

        returns the stage_id (int) of the newly created 'Stage'.
        """
        url = _url_from_args('shotList', shotlist_id, 'addStage')
        jsondata = json.dumps(dict(name=stagename, customId=custom_stage_id, position=position))
        stageid_str = self._rmtservice.request(url, method='PUT', body=jsondata)
        return int(stageid_str)

    def update_shotlist_remove_stage(self, shotlist_id=None, stage_id=None, custom_stage_id=None):
        """Deletes the specified 'Stage' including all its children and associated media files."""
        if shotlist_id is not None and stage_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'delete')
            self._rmtservice.request(url, method='DELETE')
        elif custom_stage_id is not None:
            url = _url_from_args('shotList', 'stage_c', 'delete')
            jsondata = json.dumps(dict(customId=custom_stage_id))
            self._rmtservice.request(url, method='DELETE', body=jsondata)
        else:
            raise Exception(_ERROR_MSG_STAGE_IDS)

    def update_shotlist_textcontainer(self, shotlist_id, textcontainer_id, text):
        """Updates the text of the specified `textcontainer_id`.

        This method will set the given `text` on the specified `textcontainer_id`
        located in the given 'ShotList'. The `textcontainer_id` can be received
        by using the method get_textcontainers(..).
        Use None for the `text` value in order to clear the textcontainer.

        Please note that this method will throw an Exception if the given text
        does not fit into the configured width and height of the textcontainer.
        """
        url = _url_from_args('shotList', shotlist_id, 'tc', textcontainer_id, 'update')
        jsondata = json.dumps(dict(text=text))
        self._rmtservice.request(url, method='PUT', body=jsondata)

    def update_shotlist_textpool(self, shotlist_id, textpool_id, entry_id):
        """Updates the text entry of the specified `textpool_id`.

        This method will set the given `entry_id` on the specified `textpool_id`
        located in the given 'ShotList'. The `textpool_id` and its available text
        entries can be received by using the method get_textpools(..).
        On the GUI-Client a TextPool is displayed as a drop-down menu where the
        text entries are the available options to select from.

        In order to clear a selected entry without setting a new one use
        constants.EMPTYVALUE for the `entry_id`.
        """
        url = _url_from_args('shotList', shotlist_id, 'tp', textpool_id, 'update', entry_id)
        self._rmtservice.request(url, method='PUT')

    def update_shotlist_assettextpool(self, shotlist_id, pool_id,
                                      asset_list_id=None, asset_id=None, custom_asset_id=None):
        """Sets the specified Asset on the specified `pool_id`.

        This method will set the specified Asset on the specified `pool_id`
        located in the given 'ShotList'. The `pool_id` can be received by using
        the method get_assettextpools(..).
        On the GUI-Client an AssetTextPool is displayed as a drop-down menu.
        It always belongs to an AssetList and the Assets of that AssetList
        are the available options to select from. The connected AssetList
        for the AssetTextPool can also be received from the method
        get_assettextpools(..). If an Asset is specified that does not
        belong to the connected AssetList of this AssetTextPool then an
        Exception is thrown.

        In order to set no selected Asset for this AssetTextPool use
        constants.EMPTYVALUE as value for `asset_id`. In that case you
        must still specify the `asset_list_id` and you cannot use the
        `custom_asset_id`.
        """
        dct = {}
        if asset_list_id is not None and asset_id is not None:
            dct['assetListId'] = asset_list_id
            dct['assetId'] = asset_id
        elif custom_asset_id is not None:
            dct['customAssetId'] = custom_asset_id
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)
        url = _url_from_args('shotList', shotlist_id, 'atp', pool_id, 'update')
        jsondata = json.dumps(dct)
        self._rmtservice.request(url, method='PUT', body=jsondata)

    # ******************************************** download  ******************************************************

    def download_assetfile(self, filepath, appendage_id, fileversion,
                           asset_list_id=None, asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Downloads the file of the specified 'Appendage'.

        If the Appendage contains an image sequence or folder then this method
        cannot be used to download the original files but THUMB and PREVIEW
        versions (if available) can be downloaded with this method. In order
        to download the original files of an image sequence or folder the methods
        download_assetimageseq(..) / download_assetfolder(..) can be used. If you
        have a reference to an 'Appendage' and you don't know the content
        you can check its `appendagetype` attribute which contains one of the
        constants.APPENDAGE_TYPE_* constants.

        `filepath` - The destination file path. Can be either a str or a byte-like
        object as expected by the native 'open' function of Python. The ´filepath´
        must not already exist otherwise an Exception is thrown. Parent folders are
        created if necessary.

        `fileversion` - possible values are the constants constants.FILEVERSION_*.
        Use 'Appendage'.isonline to check whether the ORIGINAL version
        is available. Use 'Appendage'.haspreviews to check whether the PREVIEW
        and THUMB versions are available for download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during downloading the file the incomplete file gets
        deleted but eventually created folders remain.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if os.path.exists(filepath):
            raise Exception("Given destination filepath '" + filepath + "' already exists.")
        folderpath = os.path.dirname(filepath)
        _ensure_folder_existing(folderpath)
        if asset_list_id is not None and asset_id is not None:
            url = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'dl', fileversion)
            self._rmtservice.download(url, filepath)
        elif custom_asset_id is not None:
            url = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'dl', fileversion)
            jsondata = json.dumps(dict(customId=custom_asset_id))
            self._rmtservice.download(url, filepath, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def download_assetimageseq(self, folderpath, appendage_id,
                               asset_list_id=None, asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Downloads files of an image sequence into the specified folder.

        This method can only be used to download the original uploaded files
        of an image sequence. So `appendagetype` of the specified 'Appendage'
        must equal APPENDAGETYPE_IMAGESEQ. In order to download the PREVIEW or
        THUMB version of an image sequence the method download_assetfile(..)
        must be used.

        `folderpath` - The destination folder path must be a str object. If it
        doesn't already exist it will be created including parent folders as
        necessary. If it already exists as a regular file then an Exception is
        thrown. If the destination folder already exists and is not empty then
        existing files and sub folders are ignored. Already existing image files
        will be skipped. The latter means you can also use this method to
        resume a previously interrupted download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during downloading the image sequence already
        downloaded files remain on disk.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        _ensure_folder_existing(folderpath)
        if asset_list_id is not None and asset_id is not None:
            urlgetlist = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                        jobordef['isDefId'], 'appendage', appendage_id, 'getImageNames')
            filelist_str = self._rmtservice.request(urlgetlist)
            filelist = json.loads(filelist_str)
            urlgetfile = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                        jobordef['isDefId'], 'appendage', appendage_id, 'dl-imageseq')
            for filename in filelist:
                filepath = os.path.join(folderpath, filename)
                if not os.path.exists(filepath):
                    jsondata = json.dumps(dict(filename=filename))
                    self._rmtservice.download(urlgetfile, filepath, body=jsondata)
        elif custom_asset_id is not None:
            urlgetlist = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'getImageNames')
            jsondata = json.dumps(dict(customId=custom_asset_id))
            filelist_str = self._rmtservice.request(urlgetlist, body=jsondata)
            filelist = json.loads(filelist_str)
            urlgetfile = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'dl-imageseq')
            for filename in filelist:
                filepath = os.path.join(folderpath, filename)
                if not os.path.exists(filepath):
                    jsondata = json.dumps(dict(customId=custom_asset_id, filename=filename))
                    self._rmtservice.download(urlgetfile, filepath, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

    def download_assetfolder(self, folderpath, appendage_id,
                             asset_list_id=None, asset_id=None, custom_asset_id=None, job_id=None, jobdef_id=None):
        """Downloads files of an appendage folder into the specified folder.

        This method can only be used to download the original uploaded files
        of an appendage folder. So `appendagetype` of the specified 'Appendage'
        must equal APPENDAGETYPE_FOLDER. In order to download the PREVIEW or
        THUMB version of an appendage folder the method download_assetfile(..)
        must be used.

        `folderpath` - The destination folder path must be a str object. If it
        doesn't already exist it will be created including parent folders as
        necessary. If it already exists as a regular file then an Exception is
        thrown. If the destination folder already exists and is not empty then
        existing files with the same size are skipped. Existing files with
        a different size will be overwritten. That means you can also use this
        method to resume a previously interrupted download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during the download then already downloaded files
        remain on disk.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        _ensure_folder_existing(folderpath)
        dctbody = dict()
        if asset_list_id is not None and asset_id is not None:
            urlgetlist = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                        jobordef['isDefId'], 'appendage', appendage_id, 'folder', 'getpaths')
            pathlist_str = self._rmtservice.request(urlgetlist)
            urlgetfile = _url_from_args('assetList', asset_list_id, 'asset', asset_id, 'job', jobordef['id'],
                                        jobordef['isDefId'], 'appendage', appendage_id, 'folder', 'getfile')

        elif custom_asset_id is not None:
            dctbody['customId'] = custom_asset_id
            urlgetlist = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'folder', 'getpaths')
            pathlist_str = self._rmtservice.request(urlgetlist, body=json.dumps(dctbody))
            urlgetfile = _url_from_args('assetList', 'asset_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'folder', 'getfile')
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        pathlist = json.loads(pathlist_str)['items']
        for pathdict in pathlist:
            pathelements = pathdict['pathElements']
            isfolder = pathdict['isFolder']
            abspath = os.path.join(folderpath, *pathelements)
            if isfolder:
                _ensure_folder_existing(abspath)
            else:
                size = pathdict['size']
                if not _check_file_samesize_existing(abspath, size):
                    dctbody['pathElements'] = pathelements
                    _ensure_folder_existing(os.path.dirname(abspath))
                    self._rmtservice.download(urlgetfile, abspath, body=json.dumps(dctbody))

    def download_shotfile(self, filepath, appendage_id, fileversion, shotlist_id=None, stage_id=None, shot_id=None,
                          custom_shot_id=None, job_id=None, jobdef_id=None):
        """Downloads the file of the specified 'Appendage'.

        If the Appendage contains an image sequence or folder then this method
        cannot be used to download the original files but THUMB and PREVIEW
        versions (if available) can be downloaded with this method. In order
        to download the original files of an image sequence or folder the methods
        download_shotimageseq(..) / download_shotfolder(..) can be used. If you
        have a reference to an 'Appendage' and you don't know the content
        you can check its `appendagetype` attribute which contains one of the
        constants.APPENDAGE_TYPE_* constants.

        `filepath` - The destination file path. Can be either a str or a byte-like
        object as expected by the native 'open' function of Python. The ´filepath´
        must not already exist otherwise an Exception is thrown. Parent folders are
        created if necessary.

        `fileversion` - possible values are the constants constants.FILEVERSION_*.
        Use 'Appendage'.isonline to check whether the ORIGINAL version
        is available. Use 'Appendage'.haspreviews to check whether the PREVIEW
        and THUMB versions are available for download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during downloading the file the incomplete file gets
        deleted but eventually created folders remain.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        if os.path.exists(filepath):
            raise Exception("Given destination filepath '" + filepath + "' already exists.")
        folderpath = os.path.dirname(filepath)
        _ensure_folder_existing(folderpath)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job', jobordef['id'],
                                 jobordef['isDefId'], 'appendage', appendage_id, 'dl', fileversion)
            self._rmtservice.download(url, filepath)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                 'appendage', appendage_id, 'dl', fileversion)
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.download(url, filepath, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def download_shotimageseq(self, folderpath, appendage_id, shotlist_id=None, stage_id=None, shot_id=None,
                              custom_shot_id=None, job_id=None, jobdef_id=None):
        """Downloads of files of an image sequence into the specified folder.

        This method can only be used to download the original uploaded files
        of an image sequence. So `appendagetype` of the specified 'Appendage'
        must equal APPENDAGETYPE_IMAGESEQ. In order to download the PREVIEW or
        THUMB version of an image sequence the method download_shotfile(..)
        must be used.

        `folderpath` - The destination folder path must be a str object. If it
        doesn't already exist it will be created including parent folders as
        necessary. If it already exists as a regular file then an Exception is
        thrown. If the destination folder already exists and is not empty then
        existing files and sub folders are ignored. Already existing image files
        will be skipped. The latter means you can also use this method to
        resume a previously interrupted download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during downloading the image sequence already
        downloaded files remain on disk.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        _ensure_folder_existing(folderpath)
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            urlgetlist = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                        jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'getImageNames')
            filelist_str = self._rmtservice.request(urlgetlist)
            filelist = json.loads(filelist_str)
            urlgetfile = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                        jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'dl-imageseq')
            for filename in filelist:
                filepath = os.path.join(folderpath, filename)
                if not os.path.exists(filepath):
                    jsondata = json.dumps(dict(filename=filename))
                    self._rmtservice.download(urlgetfile, filepath, body=jsondata)
        elif custom_shot_id is not None:
            urlgetlist = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'getImageNames')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            filelist_str = self._rmtservice.request(urlgetlist, body=jsondata)
            filelist = json.loads(filelist_str)
            urlgetfile = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'dl-imageseq')
            for filename in filelist:
                filepath = os.path.join(folderpath, filename)
                if not os.path.exists(filepath):
                    jsondata = json.dumps(dict(customId=custom_shot_id, filename=filename))
                    self._rmtservice.download(urlgetfile, filepath, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

    def download_shotfolder(self, folderpath, appendage_id, shotlist_id=None, stage_id=None, shot_id=None,
                            custom_shot_id=None, job_id=None, jobdef_id=None):
        """Downloads files of an appendage folder into the specified folder.

        This method can only be used to download the original uploaded files
        of an appendage folder. So `appendagetype` of the specified 'Appendage'
        must equal APPENDAGETYPE_FOLDER. In order to download the PREVIEW or
        THUMB version of an appendage folder the method download_shotfile(..)
        must be used.

        `folderpath` - The destination folder path must be a str object. If it
        doesn't already exist it will be created including parent folders as
        necessary. If it already exists as a regular file then an Exception is
        thrown. If the destination folder already exists and is not empty then
        existing files with the same size are skipped. Existing files with
        a different size will be overwritten. That means you can also use this
        method to resume a previously interrupted download.

        As for the job identification you specify either the `job_id`('Job'.jobid) OR
        the `jobdef_id`('JobDefinition'.jobdefid).

        If an Error occurs during the download then already downloaded files
        remain on disk.
        """
        jobordef = _job_or_def_id(jobdef_id, job_id)
        _ensure_folder_existing(folderpath)
        dctbody = dict()
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            urlgetlist = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                        jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'folder',
                                        'getpaths')
            pathlist_str = self._rmtservice.request(urlgetlist)
            urlgetfile = _url_from_args('shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'job',
                                        jobordef['id'], jobordef['isDefId'], 'appendage', appendage_id, 'folder',
                                        'getfile')

        elif custom_shot_id is not None:
            dctbody['customId'] = custom_shot_id
            urlgetlist = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'folder', 'getpaths')
            pathlist_str = self._rmtservice.request(urlgetlist, body=json.dumps(dctbody))
            urlgetfile = _url_from_args('shotList', 'stage', 'shot_c', 'job', jobordef['id'], jobordef['isDefId'],
                                        'appendage', appendage_id, 'folder', 'getfile')
        else:
            raise Exception(_ERROR_MSG_ASSET_IDS)

        pathlist = json.loads(pathlist_str)['items']
        for pathdict in pathlist:
            pathelements = pathdict['pathElements']
            isfolder = pathdict['isFolder']
            abspath = os.path.join(folderpath, *pathelements)
            if isfolder:
                _ensure_folder_existing(abspath)
            else:
                size = pathdict['size']
                if not _check_file_samesize_existing(abspath, size):
                    dctbody['pathElements'] = pathelements
                    _ensure_folder_existing(os.path.dirname(abspath))
                    self._rmtservice.download(urlgetfile, abspath, body=json.dumps(dctbody))

    def download_stbimage(self, filepath, stbsheet_id, shotlist_id=None, stage_id=None, shot_id=None,
                          custom_shot_id=None):
        """Downloads the image of the specified 'StbSheet'.

        `filepath` - The destination file path. Can be either a str or a byte-like
        object as expected by the native 'open' function of Python. The ´filepath´
        must not already exist otherwise an Exception is thrown. Parent folders are
        created if necessary.

        If an Error occurs during downloading the file the incomplete file gets
        deleted but eventually created folders remain.
        """
        folderpath = os.path.dirname(filepath)
        _ensure_folder_existing(folderpath)
        if os.path.exists(filepath):
            raise Exception("Given destination filepath '" + filepath + "' already exists.")
        if shotlist_id is not None and stage_id is not None and shot_id is not None:
            url = _url_from_args(
                'shotList', shotlist_id, 'stage', stage_id, 'shot', shot_id, 'stbsheet', stbsheet_id, 'dl')
            self._rmtservice.download(url, filepath)
        elif custom_shot_id is not None:
            url = _url_from_args('shotList', 'stage', 'shot_c', 'stbsheet', stbsheet_id, 'dl')
            jsondata = json.dumps(dict(customId=custom_shot_id))
            self._rmtservice.download(url, filepath, body=jsondata)
        else:
            raise Exception(_ERROR_MSG_SHOT_IDS)

            # ************************************************ goodies **********************************************************

    def create_pathmanager(self, archive_path):
        """Returns an instance of goodies.LocalArchivePathManager.

        `archive_path` (str) - Must point to the root folder of the
        configured Local Archive for a specific project. The given
        folder is correct if the sub folders original, preview and
        thumb are located directly in `archive_path`. When using
        default project paths in the Synchronization Tool (see
        the Medasto Administration Manual) the path will end with
        the project_id.

        If you're using Local Archives to access media files you
        usually create one instance of LocalArchivePathManager per
        project because each project has its own media archive.

        For more information see the doc string of
        LocalArchivePathManager in the goodies module.
        """
        result_str = self._rmtservice.request('pathManagerConfig')
        dct_path_config = json.loads(result_str)
        return goodies.LocalArchivePathManager(archive_path, dct_path_config)


# ******************************************** private methods ******************************************************


def _ensure_folder_existing(folderpath):
    """Creates the given `folderpath` if not already existing.

    Throws OSError if the folder cannot be created because it is a regular file.
    """
    if os.path.isdir(folderpath):
        return
    if os.path.isfile(folderpath):
        raise OSError("Cannot create the given folder '" + str(folderpath) +
                      "' because a file with this name already exists.")
    else:
        os.makedirs(folderpath)


def _check_file_samesize_existing(filepath, size):
    """Returns true if the given `filepath` exists, is a file and has same size as `size`.

    If filepath exists but with a different size then the filepath gets deleted and false
    is returned. If filepath doesn't exist at all then false is returned as well.

    Throws OSError if the given filepath points to a directory or if any other disk access
    related errors occur.
    """
    if os.path.isdir(filepath):
        raise OSError("Given file path '" + str(filepath) + "' exists but it is a folder.")
    if os.path.isfile(filepath):
        if os.path.getsize(filepath) == size:
            return True
        os.remove(filepath)
    return False


def _job_or_def_id(jobdef_id, job_id):
    if jobdef_id is not None:
        return {'id': jobdef_id, 'isDefId': True}
    elif job_id is not None:
        return {'id': job_id, 'isDefId': False}
    else:
        raise Exception("Neither job_id nor jobdef_id is specified.")


def _objhook_shotlist(dct):
    if 'shotListId' not in dct:
        return dct
    shotlist = domain.ShotList(
        dct['shotListId'], dct['shotListName'], dct['shotListShortName'], dct['shotListPosition'])
    if 'textContainers' in dct:
        shotlist.textcontainers = _dict_from_dictlist(dct['textContainers'], 'textContainerId', 'text')
        shotlist.textpools = _dict_from_dictlist(dct['textPools'], 'textPoolId', 'selectedEntryId')
        shotlist.assettextpools = _dict_from_dictlist(dct['assetTextPools'], 'assetTextPoolId', 'selectedAssetId')
    if 'assetRelation' in dct:
        shotlist.asset_relation = _asset_relation_from_rawjson(dct['assetRelation'])
    return shotlist


def _objhook_stage(dct):
    if 'stageId' not in dct:
        return dct
    stage = domain.Stage(
        dct['shotListId'], dct['stageId'], dct['stageCustomId'], dct['stageName'], dct['stagePosition'])
    if 'textContainers' in dct:
        stage.textcontainers = _dict_from_dictlist(dct['textContainers'], 'textContainerId', 'text')
        stage.textpools = _dict_from_dictlist(dct['textPools'], 'textPoolId', 'selectedEntryId')
        stage.assettextpools = _dict_from_dictlist(dct['assetTextPools'], 'assetTextPoolId', 'selectedAssetId')
    if 'assetRelation' in dct:
        stage.asset_relation = _asset_relation_from_rawjson(dct['assetRelation'])
    return stage


def _objhook_shot(dct):
    if 'shotId' not in dct:
        return dct
    shot = domain.Shot(dct['shotListId'], dct['stageId'], dct['stageCustomId'], dct['shotId'],
                       dct['shotCustomId'], dct['shotName'], dct['shotPosition'])
    if 'textContainers' in dct:
        shot.textcontainers = _dict_from_dictlist(dct['textContainers'], 'textContainerId', 'text')
        shot.textpools = _dict_from_dictlist(dct['textPools'], 'textPoolId', 'selectedEntryId')
        shot.assettextpools = _dict_from_dictlist(dct['assetTextPools'], 'assetTextPoolId', 'selectedAssetId')
    if 'assetRelation' in dct:
        shot.asset_relation = _asset_relation_from_rawjson(dct['assetRelation'])
    return shot


def _objhook_stbsheet(dct):
    if 'stbSheetId' not in dct:
        return dct
    stbsheet = domain.StbSheet(dct['shotListId'], dct['stageId'], dct['stageCustomId'], dct['shotId'],
                               dct['shotCustomId'], dct['stbSheetId'], dct['stbImageId'], dct['position'])
    if 'textContainers' in dct:
        stbsheet.textcontainers = _dict_from_dictlist(dct['textContainers'], 'textContainerId', 'text')
        stbsheet.textpools = _dict_from_dictlist(dct['textPools'], 'textPoolId', 'selectedEntryId')
        stbsheet.assettextpools = _dict_from_dictlist(dct['assetTextPools'], 'assetTextPoolId', 'selectedAssetId')
    return stbsheet


def _objhook_status(dct):
    return domain.Status(dct['id'], dct['fullName'], dct['shortName'], dct['colorR'], dct['colorG'], dct['colorB'])


def _objhook_jobdef(dct):
    return domain.JobDefinition(dct['id'], dct['name'], dct['headerName'], dct['doneStatusId'],
                                dct['inclAppendageForJobStatus'], dct['initStatusId'],
                                dct['statusIdsAppendageMsg'],
                                dct['statusIdsGlobalMsg'], dct['position'], dct['requiredToComplete'],
                                dct['colorR'], dct['colorG'],
                                dct['colorB'])


def _objhook_message(dct):
    return domain.Message(dct['id'], dct['datetimeInMillis'], dct['statusId'], dct['text'], dct['author'])


def _objhook_job(dctjob):
    if 'jobDef' not in dctjob:
        return dctjob
    jobdef = _objhook_jobdef(dctjob['jobDef'])
    job_entries = []
    for entry in dctjob['jobEntries']:
        if entry['isAppendage']:
            msglist = []
            for msg in entry['messages']:
                msglist.append(_objhook_message(msg))
            appendage = domain.Appendage(entry['id'], entry['fileName'], entry['frozen'], entry['hasPreviews'],
                                         entry['appendageType'], entry['mediaType'],
                                         entry['mediaOnline'], entry['size'], msglist)
            job_entries.append(appendage)
        else:
            job_entries.append(_objhook_message(entry))
    return domain.Job(dctjob['id'], jobdef, job_entries)


def _dict_from_dictlist(dictlist, keyforkey, keyforvalue):
    dct = {}
    for curdct in dictlist:
        dct[curdct[keyforkey]] = curdct[keyforvalue]
    return dct


def _asset_relation_from_rawjson(list_assetlistid_assetids):
    """Returns a new dict with the assetId-lists converted to assetId-sets. """
    dct = {}
    for dct_assetlistid_assetids in list_assetlistid_assetids:
        assetlist_id = dct_assetlistid_assetids['assetListId']
        assigned_assetids = dct_assetlistid_assetids['assignedAssetIds']
        dct[assetlist_id] = set(assigned_assetids)
    return dct


def _url_from_args(*args, sep="/"):
    url = ""
    for arg in args:
        if isinstance(arg, str):
            url = (url + arg + sep)
        else:
            url = (url + str(arg) + sep)
    return url
