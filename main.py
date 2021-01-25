import json
import os
import time
from .pcrclient import *

from hoshino import *
from nonebot import *
from hoshino import Service

plugin_path = os.path.dirname(__file__)


sv = Service("zfjbot-equipmentRemind", enable_on_default=False)

with open(os.path.join(plugin_path, "equip_data.json"), "rb") as fp:
    equip_data_json = json.load(fp)
    equip_data_dict = {}
    for item in equip_data_json["datas"]:
        equip_data_dict[item["equipmentId"]] = item["equipmentName"]

with open(os.path.join(plugin_path, "account.json")) as fp:
    account_json = json.load(fp)
    client = pcrclient(account_json)


@sv.scheduled_job("interval", minutes=5)
@sv.on_fullmatch("equip check")
async def check(bot=get_bot(), ev={}):
    while client.shouldLogin:
        await client.login()
    if os.path.exists(plugin_path + "/data.json"):
        with open(plugin_path + "/data.json", "rb") as f:
            data_save = json.loads(f.read())
    else:
        data_save = ""
    result = []
    # /clan/info
    data1 = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    res1 = await client.callapi("/clan/info", data1)
    # print("res1:", res1)
    # /clan/chat_info_list
    data2 = {
        "clan_id": res1["clan"]["detail"]["clan_id"],
        "start_message_id": 0,
        "search_date": "2099-12-31",
        "direction": 1,
        "count": 10,
        "wait_interval": 3,
        "update_message_ids": [],
        "viewer_id": client.viewer_id,
    }
    res2 = await client.callapi("/clan/chat_info_list", data2)
    # print("res2:", res2)
    clan_chat_message = res2["clan_chat_message"]
    equip_requests = res2["equip_requests"]
    users = res2["users"]
    # 只统计8小时内的
    for equip_request in equip_requests:
        for chat_message in clan_chat_message:
            if (
                chat_message["message_id"] == equip_request["message_id"]
                and int(time.time()) - int(chat_message["create_time"]) <= 8 * 3600
            ):
                # print(equip_request)
                # print(chat_message["create_time"])
                for user in users:
                    if user["viewer_id"] == chat_message["viewer_id"]:
                        # print(chat_message["viewer_id"], user["name"])
                        result.append(
                            {
                                "viewer_id": equip_request["viewer_id"],
                                "name": user["name"],
                                "equip_id": equip_request["equip_id"],
                                "request_num": equip_request["request_num"],
                                "donation_num": equip_request["donation_num"],
                                "create_time": chat_message["create_time"],
                            }
                        )
    print(result)
    remind_list = []
    if not ev:
        if data_save != {}:
            for item in result:
                if data_save.get(str(item["viewer_id"])):
                    # 新请求提醒
                    if data_save[str(item["viewer_id"])]["create_time"] != item["create_time"]:
                        remind_list.append(item)
                    # 请求将要结束提醒
                    elif (
                        0 <= int(time.time()) - item["create_time"] - 8 * 3600 <= 15 * 60 and item["donation_num"] < 10
                    ):
                        remind_list.append(item)
                else:
                    remind_list.append(item)
        else:
            for item in result:
                remind_list.append(item)
    else:
        for item in result:
            remind_list.append(item)
    for item in result:
        data_save[item["viewer_id"]] = item
    print(remind_list)
    reply = ""
    for i in range(len(remind_list)):
        reply += f"{remind_list[i]['name']}请求装备:{equip_data_dict[remind_list[i]['equip_id']]}\n目前捐助：{remind_list[i]['donation_num']}/{remind_list[i]['request_num']}\n结束时间：{time.strftime('%H:%M:%S',time.localtime(int(remind_list[i]['create_time'])+8*3600))}"
        if i != len(remind_list) - 1:
            reply += "\n"
    # 写入文件
    with open(plugin_path + "/data.json", "w", encoding="utf8") as f:
        json.dump(data_save, f, ensure_ascii=False)
    if ev:
        await bot.send(ev, f"{reply}", at_sender=True)
    elif reply:
        await bot.send_group_msg(group_id=account_json["group_id"], message=f"[CQ:at,qq=320336328]\n{reply}")
        # await bot.send_group_msg(group_id=618773789, message=f"[CQ:at,qq=320336328]\n{reply}")
    return remind_list
