# encoding:utf-8
import requests

import plugins
from bridge.reply import Reply, ReplyType
from channel.feishu.feishu_message import FeishuMessage
from plugins import *
import re
import json
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.context import Context
import uuid




@plugins.register(
    name="feishudoc",
    desire_priority=-1,
    hidden=True,
    desc="对接飞书文档",
    version="0.1",
    author="wx",
)
class Feishudoc(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[feishudoc] inited")
        self.config = super().load_config()

    def on_handle_context(self, e_context: EventContext):
        input = e_context["context"].content
        msg = e_context["context"]["msg"]
        if "飞书文档" not in input or not isinstance(msg,FeishuMessage):
            return
        logger.info("命中飞书文档插件")
        query = """下面这段用户输入中，帮我分析用户是想从飞书中查找什么内容，请以这种格式返回:{
          "query_keywords": ""
        }
        用户输入为：""" + input
        context = Context(ContextType.TEXT, query)
        context["session_id"] = uuid.uuid4()
        r = Bridge().fetch_reply_content(query, context)
        keyword = get_json(r.content.replace("\n", ""))
        logger.info(f"feishudoc keyword :{keyword}")

        token = msg.access_token
        docs = search_doc(keyword, token)
        if len(docs) <= 0:
            logger.info("搜索文档结果为空")
            reply = Reply(ReplyType.INFO, "未找到文档")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return
        for d in docs:
            id = d["docs_token"]
            title = d["title"]
            docs_type = d["docs_type"]
            logger.info(f"id:{id},title:{title},docs_type:{docs_type}")
            content = get_doc_content(id,token)
            reply = build_reply_str(id, d["docs_type"], content, keyword)
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            break


    def get_help_text(self, **kwargs):
        help_text = "暂无帮助信息"
        return help_text

def search_doc(keyword, access_token):
    # search doc
    url = "https://open.feishu.cn/open-apis/suite/docs-api/search/object"
    data = {
        "search_key": keyword,
        "count": 10,
        "offset": 0,
        # "owner_ids": ["xxx", "xxx"],
        # "chat_ids": ["xxx", "xxx"],
        "docs_types": ["doc", "doc"]  ##这里必须传两个，搞不懂为啥
    }
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    response = requests.post(url=url, data=data, headers=headers)
    if response.status_code == 200:
        res = response.json()
        if res.get("code") != 0:
            logger.error(f"[FeiShu] get doc error, code={res.get('code')}, msg={res.get('msg')}")
            return []
        else:
            return res["data"]["docs_entities"]
    else:
        logger.error(f"[FeiShu] search doc error, res={response}")


def get_doc_content(document_id, access_token):
    # get_doc_content
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/raw_content";
    headers = {
        'Authorization': f'Bearer {access_token}',
    }
    response = requests.get(url=url, headers=headers)
    if response.status_code == 200:
        res = response.json()
        if res.get("code") != 0:
            logger.error(f"[FeiShu] get doc error, code={res.get('code')}, msg={res.get('msg')}")
            return ""
        else:
            return res["data"]["content"]
    else:
        logger.error(f"[FeiShu] search doc error, res={response}")


def build_reply_str(document_id, docs_type, content, keyword):
    relpy_str = ""
    if content:
        start_index = content.find(keyword)
        if start_index < 0:
            start_index = 0
        end_index = start_index + 100
        e = content.find("\n", end_index)
        if e != -1:
            end_index = e;
        result = content[start_index: end_index]  # 进行切片操作得到截取结果
        relpy_str += result
    relpy_str = relpy_str + f"\n----------------------\n 文档地址:{get_href(document_id, docs_type)}"
    logger.info(f"飞书文档插件回复内容：{relpy_str}")
    return Reply(ReplyType.TEXT, relpy_str)


def get_href(document_id, type):
    if type in ["docx","doc"]:
        return f"https://kvzrmko3cx.feishu.cn/docx/{document_id}"
    if "sheet" == type:
        return f"https://kvzrmko3cx.feishu.cn/sheet/{document_id}"
    return ""


def fetch_access_token() -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    headers = {
        "Content-Type": "application/json"
    }
    req_body = {
        "app_id": "cli_a5167cd1f4be500d",
        "app_secret": "oouyBjnxz1oCbTnnutzjYc7z4YY8CXdB"
    }
    data = bytes(json.dumps(req_body), encoding='utf8')
    response = requests.post(url=url, data=data, headers=headers)
    if response.status_code == 200:
        res = response.json()
        if res.get("code") != 0:
            logger.error(f"[FeiShu] get tenant_access_token error, code={res.get('code')}, msg={res.get('msg')}")
            return ""
        else:
            return res.get("tenant_access_token")
    else:
        logger.error(f"[FeiShu] fetch token error, res={response}")


def get_json(str):
    # 使用正则表达式匹配JSON字符串
    match = re.search(r'\{.*\}', str)
    if match:
        json_str = match.group()
        json_data = json.loads(json_str)
        # 获取query_keywords的值
        return json_data.get("query_keywords")
    return None


#
# config["open_ai_api_key"]="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"
# input ="飞书文档中有周报和日报吗"
# query = """下面这段用户输入中，帮我分析用户是想从飞书中查找什么内容，请以这种格式返回:{
#   "query_keywords": ""
# }
# 用户输入为："""+input
# context = Context(ContextType.TEXT, query)
# context["session_id"] = uuid.uuid4()
# print(context["session_id"])
# r = Bridge().fetch_reply_content(query, context)
# keyword = get_json(r.content.replace("\n",""))
# token = fetch_access_token()
# docs = search_doc(keyword, token)
# if len(docs) <= 0:
#     print("未找到文档")
# for d in docs:
#     id = d["docs_token"]
#     print(id)
#     content = get_doc_content(id, token)
#     print(d["title"])
#     print(d["docs_type"])
#     print(content)
#     build_reply_str(id, d["docs_type"], content, keyword)
#     break
# # print(docs)
