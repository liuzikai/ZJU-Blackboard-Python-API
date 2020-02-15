import os
import sys
import requests
import json
import time
import math
import random
from termcolor import cprint
from pyquery import PyQuery
from html2text import html2text
import urllib.request


def eprint(*args, **kwargs):
    """
    cprint to STDERR
    :param args:
    :param kwargs:
    :return:
    """
    cprint(*args, file=sys.stderr, **kwargs)


class ZJUBlackboardSession:

    ALERT_FETCH_INTERVAL = 1  # [s]

    def __init__(self):
        self.s = requests.Session()
        self.base_url = "https://c.zju.edu.cn"

        self.s.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

    def login(self, encoded_pw, encoded_pw_unicode, login_uid_unicode, login_pwd_unicode):
        """
        :return: True if success, False otherwise
        """

        self.s.get(self.base_url)

        data = {
            "action": "login",
            "remote-user": "",
            "new_loc": "",
            "auth_type": "",
            "one_time_token": "",
            "encoded_pw": encoded_pw,
            "encoded_pw_unicode": encoded_pw_unicode,
            "login_uid_unicode": login_uid_unicode,
            "login_pwd_unicode": login_pwd_unicode,
            "bblangt": "null"
        }

        ret = self.s.post(url=self.base_url + "/webapps/bb-sso-BBLEARN/authValidate/customLoginFromLoginAjax",
                          data=data)

        return ret.text == "true"

    def fetch_alerts_once(self, retrieve_only):

        """
        Fetch alert raw data and return in JSON format
        :param retrieve_only: a parameter used in request data
        :return: JSON object
        """

        url = self.base_url + "/webapps/streamViewer/streamViewer"

        data = {
            "cmd": "loadStream",
            "streamName": "alerts",
            "providers": "{}",
            "forOverview": "false"
        }

        if retrieve_only:
            data["retrieve_only"] = "true"

        ret = self.s.post(url=url, data=data)
        # print(ret.text)
        if ret.status_code != 200:
            return None

        return json.loads(ret.text)

    def dismiss_alert(self, actor_id):

        """
        Dismiss an alert given the actor_id of the alert
        :param actor_id: actor_id from entry["itemSpecificData"]["notificationDetails"]["actorId"]
        :return: the status of POST
        :note:  Currently the return text always indicates error, but the dismiss may still succeeded.
                On the other hand, the dismiss may fail even the post succeeded.
        :note: inspired by stream.js in website source
        """

        dismiss_url = self.base_url + "/webapps/streamViewer/dwr_open/call/plaincall/NautilusViewService.removeRecipient.dwr"

        data = {
            "callCount": "1",
            "page": "/webapps/streamViewer/streamViewer?cmd=view&streamName=alerts&globalNavigation=false",
            "httpSessionId": self.s.cookies.get("JSESSIONID", domain="c.zju.edu.cn", path="/webapps/streamViewer"),
            "scriptSessionId": "8A22AEE4C7B3F9CA3A094735175A6B14" + str(math.floor(random.random() * 1000)),
            "c0-scriptName": "NautilusViewService",
            "c0-methodName": "removeRecipient",
            "c0-id": "0",
            "c0-param0": "string:" + str(actor_id),
            "batchId": "0",
        }

        ret = self.s.post(url=dismiss_url, data=data)
        return ret.status_code == 200

    def process_raw_entries(self, entries):

        """
        Process raw JSON entries into alerts.
        :param entries: raw JSON entries
        :return: list of alerts

        About unknown event type/content type: Instead of raising Exception,
        this function encoded the message into alert["exception"] and allow
        upper level code to handle it.
        """

        alerts = []

        for entry in entries:

            alert = {
                "title": entry["itemSpecificData"]["title"],
                "course_id": entry["se_courseId"],
                "dismiss_id": entry["itemSpecificData"]["notificationDetails"]["actorId"],
                "exception": None,
                "raw": entry
            }

            # Get the original URL
            if "se_itemUri" in entry:
                alert["url"] = self.base_url + entry["se_itemUri"]
            else:  # overdue alert may not have url
                alert["url"] = ""

            event_type = entry["extraAttribs"]["event_type"]

            # Content available
            if event_type == "CO:CO_AVAIL":
                alert["event"] = "content:available"

                content_handler = entry["itemSpecificData"]["contentDetails"]["contentHandler"]
                if content_handler == "resource/x-bb-file":
                    alert["content_type"] = "file"
                    alert["file_url"] = entry["itemSpecificData"]["contentDetails"]["contentSpecificFileData"]
                elif content_handler == "resource/x-bb-document":
                    alert["content_type"] = "document"
                    alert["doc_url"] = entry["se_itemUri"]
                elif content_handler == "resource/x-bb-blankpage":
                    alert["content_type"] = "blank"
                elif content_handler == "resource/x-bb-mediasite":
                    alert["content_type"] = "media"
                else:
                    alert["content_type"] = "unknown"
                    alert["exception"] = "Unhandled content type '%s'" % content_handler
            # Grade overdue (unsure what major type GB means...)
            elif event_type == "GB:OVERDUE":
                alert["event"] = "grade:overdue"
            # Announcement available
            elif event_type == "AN:AN_AVAIL":
                alert["event"] = "announcement:available"
                if entry["se_details"] != "":
                    alert["announcement"] = html2text(PyQuery(entry["se_details"]).find(".vtbegenerated").html())
            # Grade manual update
            elif event_type == "GB:GB_GRA_UPDATED":
                alert["event"] = "grade:manual_update"
            # Course available
            elif event_type == "CR:CR_AVAIL":
                alert["event"] = "course:available"
            # Assignment due time available
            elif event_type == "AS:DUE":
                alert["event"] = "assignment:due_available"
                alert["assignment"] = html2text(
                    PyQuery(entry["se_context"]).find(".eventTitle").html(), bodywidth=0).replace("\n", "")
            # Assignment available
            elif event_type == "AS:AS_AVAIL":
                alert["event"] = "assignment:available"
                alert["assignment"] = html2text(
                    PyQuery(entry["se_context"]).find(".eventTitle").html(), bodywidth=0).replace("\n", "")
            # Grade updated
            elif event_type == "GB:GB_ATT_UPDATED":
                alert["event"] = "grade:update"
                alert["grade"] = html2text(
                    PyQuery(entry["se_context"]).find(".eventTitle").html(), bodywidth=0).replace("\n", "")
            # Unknown type
            else:
                alert["event"] = "unknown"
                alert["exception"] = "Unhandled event type '%s'" % event_type

            alerts.append(alert)

        return alerts

    def get_raw_entries(self):
        """
        Get alert entries in the format of JSON array
        :return: list of alert entries (JSON)
        :note: inspired by stream.js in website source
        """

        ret = []

        # Access alert view for once
        data = {
            "cmd": "view",
            "streamName": "alerts",
            "globalNavigation": "false"
        }
        self.s.post(self.base_url + "/webapps/streamViewer/streamViewer", data)

        seen_ids = []
        raw = self.fetch_alerts_once(False)  # for the first retrieve, do not use retrieveOnly
        while True:
            entries = raw['sv_streamEntries']
            eprint("Fetched %d alert(s)" % len(entries), None)

            duplicate_id = False
            for entry in entries:
                if entry["se_id"] not in seen_ids:
                    seen_ids.append(entry["se_id"])
                    ret.append(entry)
                else:
                    duplicate_id = True
                    break

            if duplicate_id:
                eprint("Warning: duplicate ID detected", "yellow")
                break

            if not raw["sv_moreData"]:
                break

            time.sleep(self.ALERT_FETCH_INTERVAL)  # sleep for 3s

            raw = self.fetch_alerts_once(True)  # start from second retrieve, use retrieveOnly

        return ret

    def download_file(self, inner_url, save_path):
        """
        Download a file given its url to the given location
        :param inner_url: file url without the base url (c.zju.edu.cn)
        :param save_path: the save path of the file, and the filename is automatically determined
        :return: filename
        """

        # NOTICE the stream=True parameter
        r = self.s.get(self.base_url + inner_url, stream=True)
        r.encoding = "utf-8"

        # print("urllib.request.unquote(r.url) =", urllib.request.unquote(r.url))
        local_filename = urllib.request.unquote(r.url).split('/')[-1]  # use r.url since the page may redirect

        if not os.path.exists(save_path):
            os.makedirs(save_path)

        with open(os.path.join(save_path, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        return local_filename

    def process_document_entry(self, doc_obj, result):
        """
        Extract information from the page source with type "resource/x-bb-document".
        :param doc_obj: PyQuery object
        :param result: mutable initialized dict (see _process_document_raw())
        :return: None
        """

        for doc_div in doc_obj.children().items():

            div_class = doc_div.attr("class")

            if "vtbegenerated" in div_class:
                for doc_child in doc_div.children().items():
                    result["text"] += doc_child.text() + "\n"
            elif "contextItemDetailsHeaders" in div_class:
                self.process_document_entry(doc_div, result)
            elif "detailsLabel" in div_class:
                result["text"] += "\n" + doc_div.text() + "\n"
            elif "detailsValue" in div_class:
                self.process_document_entry(doc_div, result)
            elif "attachments" in div_class:
                doc_attachments = doc_div.children("li")
                for doc_attachment in doc_attachments.items():
                    doc_a = doc_attachment.children("a")
                    result["text"] += "    " + doc_a.text() + "\n"
                    result["attachments"].append(doc_a.attr("href"))
            else:
                result["exception"] += "[_process_document_entry] Unhandled Class %s\n" % div_class

    def process_document_raw(self, raw_text):
        """
        Process the page source with type "resource/x-bb-document".
        Please leave this function alone for unit test.
        :param raw_text: string of document content
        :return: a dict containing some information
        """

        ret = {
            "title": "",
            "text": "",
            "attachments": [],
            "exception": ""
        }

        doc = PyQuery(str(raw_text))

        ret["title"] = doc("#pageTitleText").text().replace("\\n', ' ", "").strip()
        self.process_document_entry(doc(".details"), ret)

        return ret

    def interpret_document(self, inner_url):
        """
        Given an url of the type "resource/x-bb-document," look into it and extract necessary information.
        :param inner_url: page url without the base url (c.zju.edu.cn)
        :return: a dict containing some information (see _process_document_raw)
        """

        ret = self.s.get(url=self.base_url + inner_url,)

        if ret.status_code != 200:
            return None

        return self.process_document_raw(ret.text)

    def process_assignment_page_raw(self, raw_text):
        """
        Process the page source with type "resource/x-bb-assignment".
        Please leave this function alone for unit test.
        :param raw_text: string of document content
        :return: a dict containing some information
        """

        ret = {
            "content": "",
            "attachments": []
        }

        doc = PyQuery(str(raw_text))

        content_entries = doc("#stepcontent1")("ol")("li")

        for html_entry in content_entries:
            entry = PyQuery(html_entry)
            ret["content"] += html2text(entry.html())
            if entry.attr("id") == "instructions":
                for link in entry.find("a"):
                    if link.attrib["href"]:
                        ret["attachments"].append(link.attrib["href"])

        return ret

    def interpret_assignment_page(self, inner_url):
        """
        Given an url of the type "resource/x-bb-assignment," look into it and extract necessary information.
        :param inner_url: page url without the base url (c.zju.edu.cn)
        :return: a dict containing some information (see process_assignment_page_raw)
        """

        ret = self.s.get(url=self.base_url + inner_url)

        if ret.status_code != 200:
            return None

        return self.process_assignment_page_raw(ret.text)


if __name__ == '__main__':
    p = ZJUBlackboardSession()
    with (open("test-data/uploadAssignment", "r", encoding="utf-8")) as file:
        print(p.process_assignment_page_raw(file.read()))
