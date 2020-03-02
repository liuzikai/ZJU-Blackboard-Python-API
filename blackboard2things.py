import os
import sys
import applescript
from datetime import datetime
from termcolor import cprint
from zju_blackboard import *
from config import *


def eprint(*args, **kwargs):
    """
    cprint to STDERR
    :param args:
    :param kwargs:
    :return:
    """
    cprint(*args, file=sys.stderr, **kwargs)


def add_to_things(title, note):
    script = applescript.AppleScript("""
    on add_to_inbox(theTitle, theNote)
      tell application "Things3"
        make new to do with properties {name: theTitle, notes: theNote}
      end tell
    end add_to_inbox
    """)
    return script.call("add_to_inbox", title, note)


def add_exception_to_things(info):
    add_to_things("Handle exception in Blackboard2Things", info)


def handle_alert(s, alert):
    """
    Handle alert and generate item to Things.
    :param s: instance of ZJUBlackboardSession
    :param alert: one alert entry from inside s.process_raw_entries()
    :return: None

    About unknown event type/content type: this handler is expected to handle
    all return from the processor (s.process_raw_entries). If an alert is
    recognized as unknown in the processor, this handler must handle it
    (for now, Things item will still be generated, with exception info).
    If you don't handle a case from the processor, it's considered as you the
    programmer's problem, so an SystemError will be raised.
    """

    # Translate course name to the title
    course_name = COURSE_CODE_TO_NAME[alert["course_id"]]

    # Prepare things item
    things_title = ""
    things_note = ""

    things_title += course_name
    eprint("%s%s" % (course_name, alert["title"]), None)

    should_dismiss = True  # whether this type of message can be handled automatically

    # Content available
    if alert["event"] == "content:available":
        things_title += "content " + alert["title"] + " available"

        # File
        if alert["content_type"] == "file":
            if not DISABLE_DOWNLOAD:
                success, filename, size = s.download_file(alert["file_url"], DOWNLOAD_PATH, MAXIMAL_DOWNLOAD_SIZE)
                if success:
                    eprint("  %s downloaded" % filename, None)
                    things_note = "[INFO] %s downloaded" % filename
                else:
                    eprint("  %s is not downloaded due to large size (%d MB)" % (filename, size / 2014 / 1024),
                           None)
                    things_note = "[INFO] %s is not downloaded due to large size (%d MB)" % (
                        filename, size / 2014 / 1024)
        # Document
        elif alert["content_type"] == "document":
            things_note += "TYPE: document.\n"

            eprint("  Further look into document", None)

            doc_data = s.interpret_document(alert["doc_url"])

            if doc_data is None:
                eprint("  Failed to interpret document", "red")
                add_exception_to_things("Fail to interpret document %s" % alert["doc_url"])
                things_note += "TYPE: document. FAIL TO INTERPRET!\n"
                should_dismiss = False
            else:
                things_note += doc_data["text"]
                if not DISABLE_DOWNLOAD:
                    for download_url in doc_data["attachments"]:
                        success, filename, size = s.download_file(download_url, DOWNLOAD_PATH, MAXIMAL_DOWNLOAD_SIZE)
                        if success:
                            eprint("  %s downloaded" % filename, None)
                            things_note += "\n[INFO] %s downloaded" % filename
                        else:
                            eprint("  %s is not downloaded due to large size (%d MB)" % (filename, size / 2014 / 1024),
                                   None)
                            things_note += "\n[INFO] %s is not downloaded due to large size (%d MB)" % (
                                filename, size / 2014 / 1024)
        # Blank
        elif alert["content_type"] == "blank":
            things_note += "TYPE: blank page. See original URL.\n"
        # Media
        elif alert["content_type"] == "media":
            things_note += "TYPE: media page. See original URL.\n"
        # Forum Link
        elif alert["content_type"] == "forum_link":
            things_note += "TYPE: forum link. See original URL.\n"
        # Video
        elif alert["content_type"] == "video":
            things_note += "TYPE: video. See original URL.\n"
        # External link
        elif alert["content_type"] == "external_link":
            things_note += "TYPE: external link. See original URL.\n"
            # TODO: maybe the page can be automatically inspected as document
            # data/20200218151412.json
        # Unknown
        elif alert["content_type"] == "unknown":
            things_title += " [unknown type]"
            things_note += "EXCEPTION: " + alert["exception"] + "\n"
            eprint("  Exception from processor: %s" % alert["exception"], "red")
        else:
            raise SystemError("Unhandled content type '%s'" % alert["content_type"])
    # Grade overdue (unsure what major type GB means...)
    elif alert["event"] == "grade:overdue":
        things_title += alert["title"] + " overdue"
    # Announcement available
    elif alert["event"] == "announcement:available":
        things_title += "announcement " + alert["title"]
        if alert.get("announcement"):
            things_note += alert["announcement"] + "\n"
    # Grade manual update
    elif alert["event"] == "grade:manual_update":
        things_title += "manual score of " + alert["title"] + " updated"
    # Assignment due time available
    elif alert["event"] == "assignment:due_available":
        things_title += "assignment " + alert["assignment"] + " due time available"
    # Assignment available
    elif alert["event"] == "assignment:available":
        things_title += "assignment " + alert["assignment"] + " available"
        ret = s.interpret_assignment_page(alert["url"])
        if ret is None:
            eprint("  Failed to interpret assignment page", "red")
            add_exception_to_things("Fail to interpret assignment page %s" % alert["url"])
            things_note += "FAIL TO INTERPRET!\n"
            should_dismiss = False
        else:
            things_note += ret["content"]
            if not DISABLE_DOWNLOAD:
                for attachment in ret["attachments"]:
                    success, filename, size = s.download_file(attachment, DOWNLOAD_PATH, MAXIMAL_DOWNLOAD_SIZE)
                    if success:
                        eprint("  %s downloaded" % filename, None)
                        things_note += "\n[INFO] %s downloaded" % filename
                    else:
                        eprint("  %s is not downloaded due to large size (%d MB)" % (filename, size / 2014 / 1024),
                               None)
                        things_note += "\n[INFO] %s is not downloaded due to large size (%d MB)" % (
                            filename, size / 2014 / 1024)
    # Grade updated
    elif alert["event"] == "grade:update":
        things_title += "grade of " + alert["grade"] + " updated"
    # Course available
    elif alert["event"] == "course:available":
        things_title += "course " + alert["title"] + " available"
        things_note += "Course ID: " + alert["course_id"] + "\n"
    # Unknown
    elif alert["event"] == "unknown":
        things_title += " [unknown event] " + alert["title"]
        things_note += "EXCEPTION: " + alert["exception"] + "\n"
        eprint("  Exception from processor: %s" % alert["exception"], "red")
    else:
        raise SystemError("Unhandled event type '%s'" % alert["event"])

    # Dismiss alert
    if not DISABLE_DISMISS and should_dismiss:
        if s.dismiss_alert(alert["dismiss_id"]):
            eprint("  %s dismissed" % alert["title"], None)

        else:
            eprint("  Failed to dismiss %s" % alert["title"], "red")
    else:
        things_note += "Alert is NOT dismissed.\n"

    # Add the original url at the end
    if alert["url"] != "":
        things_note += '\n' + alert["url"]

    # Add to Things Inbox
    if not DO_NOT_ADD_TO_THINGS:
        add_to_things(things_title, things_note)


if __name__ == '__main__':

    if ENCODED_PW == "" or ENCODED_PW_UNICODE == "" or \
            LOGIN_UID_UNICODE == "" or LOGIN_PWD_UNICODE == "":
        raise ValueError("Please set your login info in config.py first")

    time_stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    s = ZJUBlackboardSession()

    # Login
    if not DISABLE_LOGIN:
        if s.login(ENCODED_PW, ENCODED_PW_UNICODE, LOGIN_UID_UNICODE, LOGIN_PWD_UNICODE):
            print("Failed to log in")
            exit(1)
        else:
            eprint("Login succeeded", None)

    # Get raw entries
    if USE_EXISTING_RAW_ENTRIES == "":  # fetched fresh data
        assert not DISABLE_LOGIN, "Login is disabled and no existing raw data is given."
        entries = s.get_raw_entries()
        if len(entries) > 0:
            # Save the raw data for future debug
            if not os.path.exists(DATA_PATH):
                os.makedirs(DATA_PATH)
            with open(os.path.join(DATA_PATH, time_stamp + '.json'), "w") as file:
                file.write(json.dumps(entries, indent=2, separators=(',', ': ')))
    else:  # use existing data
        eprint("[Debug] Using %s" % USE_EXISTING_RAW_ENTRIES, "yellow")
        with open(USE_EXISTING_RAW_ENTRIES, "r", encoding='utf-8') as entries_raw_file:
            entries = json.loads(entries_raw_file.read())

    # Process raw entries into alerts
    alerts = s.process_raw_entries(entries)

    # Check for unknown courses
    unknown_courses = []
    for alert in alerts:
        if alert["course_id"] not in COURSE_CODE_TO_NAME:
            if alert["course_id"] not in unknown_courses:
                unknown_courses.append(alert["course_id"])
    if len(unknown_courses) > 0:
        # Only handle course:available message
        for alert in alerts:
            if alert["event"] == "course:available":
                add_to_things(title="Course " + alert["title"] + " available",
                              note="Course ID: " + alert["course_id"] + "\n")
                if not DISABLE_DISMISS:
                    s.dismiss_alert(alert["dismiss_id"])
        print("New course(s) detected. Handle them first.")
    else:
        if len(alerts) > 0:
            eprint("Ready to handle %d item(s)..." % (len(alerts)), None)
            for alert in alerts:
                handle_alert(s, alert)
            print("%d item(s) processed" % len(alerts))
        else:
            print("No alert available")
