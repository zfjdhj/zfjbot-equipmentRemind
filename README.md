# zfjbot-equipmentRemind

a plugin for hoshino

## 说明

由于项目的特殊性，仅为自用，作者不负责解答任何问题。

## 使用

1. 抓包或者使用冲冲大佬的[工具](https://github.com/qq1176321897/pcrjjc2)获取登录信息。
2. 将信息填入`account.json`,没有的话就目录下新建一个。
其中`group_id`为要推送消息的群。

```json
//account.json
{
    "account": "",
    "password": "",
    "platform": 2,
    "channel": 1,
    "group_id": 1234567,
    "white_list":[
    ],
    "admin": 12345678
}
```

## 功能

想着做就做了，干脆多做几个提醒

有农场脚本的情况下不适合启用自动邀请,自动通过申请

故采用q群一键通过白名单,一键邀请白名单


| 指令 | 功能 |
| :- | :- |
| (自动推送)请求装备 | 工会内有人请求装备时进行提醒，默认@Bot管理（我） |
| equip check | 查看当前时段装备请求 |
| (自动推送)入会请求 | 有人请求加入工会时进行提醒 ~~（白名单直接放过）~~，默认@Bot管理（我） |
| invite \<uid> | 有申请则通过,无申请则邀请 |
| invite check | 查看白名单成员公会信息情况 |
| invite onekeyaccept | 一键通过白名单,无申请则邀请 |
| /pcrval <32位验证码数据> | 账号失效后过验证码 |

## 更新

2021.02.14 新增验证部分代码，冲冲佬yyds

## 感谢

部分代码参考：

<https://github.com/qq1176321897/pcrjjc2>

<https://github.com/infinityedge01/qqbot2>