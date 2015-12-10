"""Public constants for the Medasto package.

The doc strings of the corresponding service methods mention the following
constants where appropriate.
"""
__author__ = 'Michael Krotky'


LAYER_SHOTLIST = 10
LAYER_STAGE = 20
LAYER_SHOT = 30
LAYER_STBSHEET = 40

# refering to.
FILEVERSION_ORIGINAL = 1    # ..the original uploaded file
FILEVERSION_PREVIEW = 2     # ..the preview of the original file
FILEVERSION_THUMB = 3       # ..the thumbnail of the original file

# possible values of the field domain.Appendage.mediatype
# uploaded media is..
MEDIATYPE_UNKNOWN = 0   # ..not recognized (or upload not yet complete)
MEDIATYPE_IMAGE = 1     # ..an image. So FILEVERSION_PREVIEW is an image as well.
MEDIATYPE_VIDEO = 2     # ..a video. So FILEVERSION_PREVIEW is a video as well.
MEDIATYPE_AUDIO = 3     # ..an audio file. So FILEVERSION_PREVIEW is an audio file as well.
MEDIATYPE_IMAGESEQ = 4  # ..an image sequence. So FILEVERSION_PREVIEW is a video wihtout audio.


EMPTYVALUE = -1  # Some methods accept this value in order to remove an entry.
