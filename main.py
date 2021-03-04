import json
import os
import time
from .pcrclient import *

from hoshino import *
from nonebot import *

# from hoshino import Service

from asyncio import Lock

plugin_path = os.path.dirname(__file__)


sv = Service("zfjbot-equipmentRemind", enable_on_default=False)
HELP_MSG = """invite <13位uid>: 有申请则通过,无申请则邀请
invite check: 查看白名单玩家信息
invite onekeyaccept: 一键通过白名单,无申请则邀请
"""

with open(os.path.join(plugin_path, "equip_data.json"), "rb") as fp:
    equip_data_json = json.load(fp)
    equip_data_dict = {}
    for item in equip_data_json["datas"]:
        equip_data_dict[item["equipmentId"]] = item["equipmentName"]

with open(os.path.join(plugin_path, "account.json")) as fp:
    acinfo = json.load(fp)
    account_json = acinfo

client = None
captcha_lck = Lock()
bot = get_bot()
validate = None
acfirst = False


async def captchaVerifier(gt, challenge, userid):
    global acfirst
    if not acfirst:
        await captcha_lck.acquire()
        acfirst = True
    url = f"http://pcr.zfjdhj.cn/geetest/captcha/?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
    reply = f"猫猫遇到了一个问题呢，请完成以下链接中的验证内容后将第一行validate=后面的内容复制，并用指令/pcrval xxxx将内容发送给机器人完成验证\n验证链接：{url}"
    await bot.send_private_msg(user_id=acinfo["admin"], message=f"{reply}")
    # 群内通知
    await bot.send_group_msg(group_id=account_json["group_id"], message=f"[CQ:at,qq={account_json['admin']}]\n{reply}")
    await captcha_lck.acquire()
    return validate


async def errlogger(msg):
    await bot.send_private_msg(user_id=acinfo["admin"], message=f"猫猫登录错误：{msg}")


bclient = bsdkclient(acinfo, captchaVerifier, errlogger)
client = pcrclient(bclient)


@sv.on_rex("/pcrval (.*)")
async def validate(bot, ev):
    global validate
    validate = ev["match"].group(1)
    captcha_lck.release()


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
    # print(result)
    remind_list = []
    if not ev:
        if data_save != {}:
            for item in result:
                if data_save["users"].get(str(item["viewer_id"])):
                    # 新请求提醒
                    if data_save["users"][str(item["viewer_id"])]["create_time"] != item["create_time"]:
                        remind_list.append(item)
                    # 请求将要结束提醒
                    elif (
                        0 <= item["create_time"] + 8 * 3600 - int(time.time()) <= 15 * 60 and item["donation_num"] < 10
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
        data_save["users"][str(item["viewer_id"])] = item
    # print(remind_list)
    reply = ""
    for i in range(len(remind_list)):
        reply += f"{remind_list[i]['name']}请求装备:{equip_data_dict[remind_list[i]['equip_id']]}\n目前捐助：{remind_list[i]['donation_num']}/{remind_list[i]['request_num']}\n结束时间：{time.strftime('%H:%M:%S',time.localtime(int(remind_list[i]['create_time'])+8*3600))}\n=============="
        if i != len(remind_list) - 1:
            reply += "\n"
    # 写入文件
    with open(plugin_path + "/data.json", "w", encoding="utf8") as f:
        json.dump(data_save, f, ensure_ascii=False)
    if ev:
        await bot.send(ev, f"[CQ:at,qq={account_json['admin']}]\n{reply}")
    elif reply:
        await bot.send_group_msg(
            group_id=account_json["group_id"], message=f"[CQ:at,qq={account_json['admin']}]\n{reply}"
        )
        await bot.send_group_msg(group_id=618773789, message=f"[CQ:at,qq={account_json['admin']}]\n{reply}")
    await invite_auto()
    return remind_list


async def invite_auto(bot=get_bot(), ev={}):
    msg = ""
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    while client.shouldLogin:
        await client.login()
    if os.path.exists(plugin_path + "/data.json"):
        with open(plugin_path + "/data.json", "rb") as f:
            data_save = json.loads(f.read())
    else:
        data_save = ""
    # 获取游戏内信息
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    member_list = {}
    if clan_info.get("clan"):
        for item in clan_info["clan"]["members"]:
            member_list[item["viewer_id"]] = item["name"]
    clan_join_request_list_data = {
        "clan_id": clan_info["clan"]["detail"]["clan_id"],
        "page": 0,
        "oldest_time": 0,
        "viewer_id": client.viewer_id,
    }
    join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
    # print("join_request_list", join_request_list)
    reruest_list = [item["viewer_id"] for item in join_request_list["list"]]
    # print(reruest_list)
    for item in join_request_list["list"]:
        # 自动同意,想要启用自动同意取消注释即可,懒得写开关了
        # if item["viewer_id"] in white_list:
        #     clan_join_request_accept_data = {
        #         "request_viewer_id": item["viewer_id"],
        #         "clan_id": clan_info["clan"]["detail"]["clan_id"],
        #         "viewer_id": client.viewer_id,
        #     }
        #     clan_join_request_accept = await client.callapi("/clan/join_request_accept", clan_join_request_accept_data)
        #     print(f"同意{item['name']}加入公会")
        #     msg+=f"哦,是猫猫的好朋友{item['name']}来了,已自动同意加入公会{clan_info['clan']['detail']['clan_name']}"
        #     request_count-=1
        #     print("clan_join_request_accept", clan_join_request_accept)
        # else:
        # if data_save.get('invite_list'):
        if data_save["invite_list"].get(str(item["viewer_id"])):
            # 有效申请
            print(time.time() - int(data_save["invite_list"][str(item["viewer_id"])]["create_time"]))
            print("is_old", data_save["invite_list"][str(item["viewer_id"])]["old"])
            if (
                time.time() - int(data_save["invite_list"][str(item["viewer_id"])]["create_time"]) < 10 * 60
                or data_save["invite_list"][str(item["viewer_id"])]["old"]
            ):
                data_save["invite_list"][str(item["viewer_id"])]["old"] = False
                msg += f"嗯? {item['name']} 申请加入公会,猫猫要怎么做呢?\nuid:{item['viewer_id']}"
                print("msg:", msg)
        else:
            # 新的申请
            data_save["invite_list"][str(item["viewer_id"])]["old"] = False
            msg += f"嗯? {item['name']} 申请加入公会,猫猫要怎么做呢?\nuid:{item['viewer_id']}"
            data_save["invite_list"][str(item["viewer_id"])] = {"create_time": int(time.time())}
        with open(plugin_path + "/data.json", "w", encoding="utf8") as f:
            json.dump(data_save, f, ensure_ascii=False)
    # 过期申请
    for item in data_save["invite_list"]:
        if item not in reruest_list:
            data_save["invite_list"][item]["old"] = True
    if msg != "":
        msg += f"\n================\ninvite <uid>: 有申请则通过,无申请则邀请"
    if ev:
        await bot.send(ev, f"{msg}", at_sender=True)
    elif msg:
        await bot.send_group_msg(
            group_id=account_json["group_id"], message=f"[CQ:at,qq={account_json['admin']}]\n{msg}"
        )
        await bot.send_group_msg(group_id=618773789, message=f"[CQ:at,qq={account_json['admin']}]\n{msg}")
    # 自动邀请,鸽了
    return


async def invite(uid: str) -> str:
    # 确认正确的uid
    is_accept = False
    res = ""
    # if uid in white_list:
    #     # 同意加入公会
    #     is_accept=True
    # else:
    user_info = await client.callapi(
        "/profile/get_profile", {"target_viewer_id": int(uid), "viewer_id": client.viewer_id}
    )
    # print(user_info)
    if user_info.get("user_info"):
        # print(user_info)
        if user_info["clan_name"] != "":
            res = f"error: {user_info['user_info']['user_name']}已有公会{user_info['clan_name']}"
        else:
            # 同意加入公会
            is_accept = True
    else:
        res = "error: uid有误,请检查后重试"
    # 获取游戏内信息
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    if is_accept:
        # 已发起申请
        clan_join_request_list_data = {
            "clan_id": clan_info["clan"]["detail"]["clan_id"],
            "page": 0,
            "oldest_time": 0,
            "viewer_id": client.viewer_id,
        }
        join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
        # print("join_request_list", join_request_list)
        is_request = False
        for item in join_request_list["list"]:
            if item == uid:
                is_request = True
                clan_join_request_accept_data = {
                    "request_viewer_id": int(uid),
                    "clan_id": clan_info["clan"]["detail"]["clan_id"],
                    "viewer_id": client.viewer_id,
                }
                clan_join_request_accept = await client.callapi(
                    "/clan/join_request_accept", clan_join_request_accept_data
                )
                res += f"哦,是猫猫的好朋友{user_info['user_info']['user_name']}来了,已同意加入公会{clan_info['clan']['detail']['clan_name']}"
                # print("clan_join_request_accept", clan_join_request_accept)
                break
        # 猫猫进行邀请
        if not is_request:
            clan_info = await client.callapi("/clan/info", clan_info_data)
            member_list = {}
            if clan_info.get("clan"):
                for item in clan_info["clan"]["members"]:
                    member_list[item["viewer_id"]] = item["name"]
            invite_user_list = await client.callapi("/clan/invite_user_list", clan_join_request_list_data)
            # print("invite_user_list", invite_user_list)
            new_invite_user_list = [item["viewer_id"] for item in invite_user_list["list"]]
            # print("new_invite_user_list:", new_invite_user_list)
            if not int(uid) in new_invite_user_list:
                clan_invite_data = {
                    "invited_viewer_id": int(uid),
                    "invite_message": "猫猫邀请您加入公会一起玩耍哦",
                    "viewer_id": client.viewer_id,
                }
                clan_invite = await client.callapi("/clan/invite", clan_invite_data)
                # print("clan_invite:", clan_invite)
                res = f"猫猫已经对{user_info['user_info']['user_name']}发起公会邀请"
            else:
                res = f"猫猫之前已经发起了邀请,但是{user_info['user_info']['user_name']}没有理睬猫猫"
    return res


async def invite_check():
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    res = "白名单用户信息:"
    for item in white_list:
        while client.shouldLogin:
            await client.login()
        user_info = await client.callapi(
            "/profile/get_profile", {"target_viewer_id": item, "viewer_id": client.viewer_id}
        )
        if user_info["clan_name"] != "":
            res += f"\n{user_info['user_info']['user_name']}已加入公会：{user_info['clan_name']}"
        else:
            res += f"\n{user_info['user_info']['user_name']}尚未加入任何公会"
    clan_info_data = {
        "clan_id": 0,
        "get_user_equip": 1,
        "viewer_id": client.viewer_id,
    }
    clan_info = await client.callapi("/clan/info", clan_info_data)
    clan_join_request_list_data = {
        "clan_id": clan_info["clan"]["detail"]["clan_id"],
        "page": 0,
        "oldest_time": 0,
        "viewer_id": client.viewer_id,
    }
    join_request_list = await client.callapi("/clan/join_request_list", clan_join_request_list_data)
    # print("join_request_list", join_request_list)
    if len(join_request_list["list"]) > 0:
        res += "\n陌生人信息:"
        for item in join_request_list["list"]:
            res += f"\n{item['name']} uid: {item['viewer_id']}"
    return res


async def invite_onekeyaccept():
    with open(os.path.join(plugin_path, "account.json")) as fp:
        config_json = json.load(fp)
    white_list = config_json["white_list"]
    res = "invite 一键邀请:"
    for item in white_list:
        while client.shouldLogin:
            await client.login()
        res += "\n"
        res += await invite(item)
    return res


@sv.on_prefix("invite")
async def invite_main(bot=get_bot(), ev={}):
    args = ev.message.extract_plain_text().split()
    msg = ""
    # user_id = ev.user_id
    is_admin = priv.check_priv(ev, priv.SUPERUSER)
    if len(args) == 0:
        msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    elif len(args) == 1:
        while client.shouldLogin:
            await client.login()
        if len(args[0]) == 13:
            if is_admin:
                msg = await invite(args[0])
            else:
                msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
        elif args[0] == "check":
            msg = await invite_check()
            pass
        elif args[0] == "onekeyaccept":
            msg = await invite_onekeyaccept()
            pass
        else:
            msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    else:
        msg = f"猫猫不懂耶~\n可用命令：\n{HELP_MSG}"
    await bot.send(ev, msg)
    return
