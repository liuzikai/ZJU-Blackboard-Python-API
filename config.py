import os

# User
ENCODED_PW = ""
ENCODED_PW_UNICODE = ""
LOGIN_UID_UNICODE = ""
LOGIN_PWD_UNICODE = ""

# Options
CURR_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(CURR_PATH, "data")
DOWNLOAD_PATH = os.path.join(CURR_PATH, "downloads")
COURSE_CODE_TO_NAME = {
    # 2019 Spring
    "_4069_1": "CALC: ",
    "_4066_1": "DISC: ",
    "_4121_1": "PHYS: ",
    "_4058_1": "PHYS: ",
    "_4060_1": "ECON: ",
    "_4101_1": "ECE: ",
}

# Debug Options
DISABLE_LOGIN = False  # @default: False. If login is disabled, program may not have access to download file
USE_EXISTING_RAW_ENTRIES = ""  # @default: ""
DISABLE_DISMISS = False  # @default: False
DISABLE_DOWNLOAD = False  # @default: False
DO_NOT_ADD_TO_THINGS = False  # @default: False
