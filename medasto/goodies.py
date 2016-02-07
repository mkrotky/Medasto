from . import constants
import os.path

__author__ = 'Michael Krotky'


class LocalArchivePathManager:
    """Helper class for creating path objects to a Medasto Local Archive.

    Medasto provides a Synchronisation Tool which can maintain a copy of the project
    media on a local server. So clients can access these files much faster via a
    LAN connection.
    The folder structure of this Local Archive is not organized in a human readable
    way. This helper class can create the paths to the desired media by simply
    supplying familiar method parameters.

    An object is instantiated with medasto.clientservice.ClientService.create_pathmanager(..).
    A ClientService object has access to the Medasto Server and from there the
    LocalArchivePathManager class needs some folder names and file extensions in order
    to create an instance. So you never create an object of this class directly.

    PLEASE NOTE: If you need access to the project media files, with the Python-API you
    have always the option to download the files manually with the download_XX(..)
    methods of the ClientService or to access them through a Local Archive (should one
    be available to the API-Client). Of course if Medasto is running in the operation
    mode DROP-OVER then original media files get deleted after a few days and you are
    forced to use the Local Archive (which usually receives the files before they get
    deleted on the server).

    If you download the files manually you can simply rely on having a complete file,
    folder or image sequence when the download method returns without Exception.
    But if you choose to work with a Local Archive you must carefully check the
    path objects returned by one of the methods local_archive_path_XX(). Just checking
    for the presence of the file is not enough. Though the Synchronisation Tool is
    downloading huge media files with the help of a temp file there is always a
    chance of unlucky timing where you could encounter an incomplete media. This
    depends on the file system implementation. And on top of that we have also
    special cases like image sequences where each image is downloaded individually.
    Apart from a common path.exists check you can compare the size of a single
    file with the medasto.domain.Appendage.size field. Make sure to compare with the
    actual file size and not the file size a file is occupying on the
    filesystem. If the Appendage contains an image sequence then its size field
    will contain the sum of all image files in bytes. In case of an appendage folder
    the size field holds the sum of all files within that folder (recursive). So this
    can be used to validate an image sequence or appendage folder as well.
    Appendage.isonline and .isuploadcomplete might be helpful too.
    """

    def __init__(self, archive_path, dct_config):
        """Not to be instantiated directly!

        Please use medasto.clientservice.ClientService.create_pathmanager(..).
        """
        self.archive_path = archive_path
        self._FOLDERNAME_ASSET = dct_config['FOLDERNAME_ASSET']
        self._FOLDERNAME_SHOT = dct_config['FOLDERNAME_SHOT']
        self._FOLDERNAME_ORIGINAL = dct_config['FOLDERNAME_ORIGINAL']
        self._FOLDERNAME_PREVIEW = dct_config['FOLDERNAME_PREVIEW']
        self._FOLDERNAME_THUMB = dct_config['FOLDERNAME_THUMB']
        self._FOLDERNAME_STB = dct_config['FOLDERNAME_STB']
        self._thumbFileExt = dct_config['thumbFileExt']
        self._videoPreviewFileExt = dct_config['videoPreviewFileExt']
        self._audioPreviewFileExt = dct_config['audioPreviewFileExt']
        self._imagePreviewFileExt = dct_config['imagePreviewFileExt']
        self._stbImageFileExt = dct_config['stbImageFileExt']

    def local_archive_path_asset(self, assetlist_id, asset_id, appendage_id, mediatype, filename, fileversion):
        """Returns the path for the specified domain.Appendage which belongs to an Asset.

        Should you have trouble understanding the following parameters please
        have a look at the doc string of the domain module. There you can
        find the structure of a project.

        If the Appendage contains an image sequence or folder instead of a single
        file then the returned path leads to the folder containing the files.

        `assetlist_id` - from the AssetList which contains the `asset_id`. The
        method ClientService.get_asset_list(..) includes this assetlist_id too.

        `asset_Id` - from the Asset which contains the 'Appendage'(`appendage_id`).

        The following 3 parameters can be taken from the 'Appendage' which is
        included in the 'Job' of the specified asset_id. The 'Job' itself can be
        received with ClientService.get_assetjob(..).
        `appendage_id`
        `mediatype`
        `filename`

        `fileversion` - one of the medasto.constants.FILEVERSION_XX.

        IMPORTANT:
        If you specify FILEVERSION_PREVIEW and the given mediatype is UNKNOWN
        then an Exception is thrown. Without mediatype the PathManager cannot
        know whether the preview is a jpg-image, mp4-video or mp3-audiofile
        and therefore the path cannot be determined.
        If you request FILEVERSION_ORIGINAL or ..THUMB then the `mediatype`
        is ignored. You can then specify an arbitrary value or simply None if
        you want.
        """
        foldername_fileversion = self._foldername_fileversion(fileversion)
        nameondisk = self._nameondisk_appendage(appendage_id, filename, fileversion, mediatype)
        return os.path.join(self.archive_path,
                            foldername_fileversion,
                            self._FOLDERNAME_ASSET,
                            str(assetlist_id),
                            str(asset_id),
                            nameondisk
                            )

    def local_archive_path_shot(self, shotlist_id, stage_id, shot_id, appendage_id, mediatype, filename, fileversion):
        """Returns the path for the specified domain.Appendage which belongs to a domain.Shot.

        Should you have trouble understanding the following parameters please
        have a look at the doc string of the domain module. There you can
        find the structure of a project.

        If the Appendage contains an image sequence or folder instead of a single
        file then the returned path leads to the folder containing the files.

        `shotlist_id` - from the 'ShotList' which contains the `stage_id` and
        the `shot_id`. The methods mentioned in the `shot_id` section below
        include this id too.

        `stage_id` - from the 'Stage' which contains the 'Shot'(`shot_id`).
        The methods mentioned in the `shot_id` section below include this id too.

        `shot_id` - from the 'Shot' which contains the 'Appendage'(`appendage_id`).
        The methods ClientService.get_shots_from_XX(..) and .get_shot(..) return
        'Shot' objects which include this shot_id and the stage_id and shotlist_id
        as well.

        The following 3 parameters can be taken from the 'Appendage' which is
        included in the 'Job' of the specified shot_id. The 'Job' itself can be
        received with ClientService.get_shotjob(..).
        `appendage_id`
        `mediatype`
        `filename`

        `fileversion` - one of the medasto.constants.FILEVERSION_XX.

        IMPORTANT:
        If you specify FILEVERSION_PREVIEW and the given mediatype is UNKNOWN
        then an Exception is thrown. Without mediatype the PathManager cannot
        know whether the preview is a jpg-image, mp4-video or mp3-audiofile
        and therefore the path cannot be determined.
        If you request FILEVERSION_ORIGINAL or ..THUMB then the `mediatype`
        is ignored. You can then specify an arbitrary value or simply None if
        you want.
        """
        foldername_fileversion = self._foldername_fileversion(fileversion)
        nameondisk = self._nameondisk_appendage(appendage_id, filename, fileversion, mediatype)
        return os.path.join(self.archive_path,
                            foldername_fileversion,
                            self._FOLDERNAME_SHOT,
                            str(shotlist_id),
                            str(stage_id),
                            str(shot_id),
                            nameondisk
                            )

    def local_archive_path_stbimage(self, shotlist_id, stbimage_id):
        """Returns the path for the specified `stbimage_id`.

        Should you have trouble understanding the following parameters please
        have a look at the doc string of the domain module. There you can
        find the structure of a project.

        `shotlist_id` - from the 'ShotList' which contains the `stbimage_id`

        `stbimage_id` - This id belongs to an 'StbSheet' object which can be
        received with the methods ClientService.get_stbsheets(..)
        and. get_stbsheet(..).
        """
        return os.path.join(self.archive_path,
                            self._FOLDERNAME_ORIGINAL,
                            self._FOLDERNAME_SHOT,
                            str(shotlist_id),
                            self._FOLDERNAME_STB,
                            self._nameondisk_stbimage(stbimage_id)
                            )

    def _foldername_fileversion(self, fileversion):
        if fileversion == constants.FILEVERSION_ORIGINAL:
            return self._FOLDERNAME_ORIGINAL
        elif fileversion == constants.FILEVERSION_PREVIEW:
            return self._FOLDERNAME_PREVIEW
        elif fileversion == constants.FILEVERSION_THUMB:
            return self._FOLDERNAME_THUMB

    def _file_extension(self, filename):
        """Returns the string after the last '.' of the given filename or an
        empty string if `filename` is None or empty or the '.' occurs as the
        last character in the `filename`.
        """
        if filename is None or len(filename) == 0:
            return ""
        index = filename.rfind('.')
        if index == -1:
            return ""
        return filename[index+1:]

    def _file_basename(self, filename):
        """Returns the String before the last '.' of the given filename. If the
        `filename` is None or empty or the '.' occurs as first character in
        the `filename` then an emtpy string is returned. If the `filename`
        does not contain a '.' then it is returned as is.
        """
        if filename is None or len(filename) == 0:
            return ""
        index = filename.rfind('.')
        if index == -1:
            return filename
        return filename[:index]

    def _nameondisk_appendage(self, appendage_id, filename, fileversion, mediatype):
        """Returns the filename for the given mediatype as stored in the local archive.

        If fileversion is PREVIEW then the mediatype must NOT be UNKNOWN. If fileversion
        is THUMB or ORIGINAL then the mediatype parameter is ignored. In case
        of MEDIATYPE_IMAGESEQ the folder name containing the images is returned.
        Please keep also in mind that no thumbnail exists for audio files.
        """
        base_name_new = self._file_basename(filename) + '_' + str(appendage_id)
        if fileversion == constants.FILEVERSION_ORIGINAL:
            file_ext = self._file_extension(filename)
            if len(file_ext) == 0:
                return base_name_new
            else:
                return base_name_new + '.' + file_ext
        elif fileversion == constants.FILEVERSION_PREVIEW:
            if mediatype == constants.MEDIATYPE_VIDEO:
                return base_name_new + '.' + self._videoPreviewFileExt
            elif mediatype == constants.MEDIATYPE_IMAGE:
                return base_name_new + '.' + self._imagePreviewFileExt
            elif mediatype == constants.MEDIATYPE_AUDIO:
                return base_name_new + '.' + self._audioPreviewFileExt
            elif mediatype == constants.MEDIATYPE_IMAGESEQ:
                return base_name_new + '.' + self._videoPreviewFileExt
            else:
                # with UNKNOWN mediatype it is not possible to determine the preview
                # filename. So fail asap..
                raise Exception("Cannot determine the filename for the PREVIEW because the mediatype is UNKNOWN")
        elif fileversion == constants.FILEVERSION_THUMB:
            return base_name_new + '.' + self._thumbFileExt
        else:
            raise Exception("Unknown fileversion: " + fileversion)

    def _nameondisk_stbimage(self, stbimage_id):
        return str(stbimage_id) + '.' + self._stbImageFileExt
