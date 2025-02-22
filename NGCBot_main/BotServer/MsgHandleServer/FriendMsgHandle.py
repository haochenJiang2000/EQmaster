from BotServer.BotFunction.InterfaceFunction import *
from ApiServer.AiServer.AiDialogue import AiDialogue
from BotServer.BotFunction.JudgeFuncion import *
from DbServer.DbMainServer import DbMainServer
import xml.etree.ElementTree as ET
import Config.ConfigServer as Cs
from OutPut.outPut import op
from threading import Thread
import time


class FriendMsgHandle:
    def __init__(self, wcf):
        """
        关键词拉群 yes
        好友消息转发给超管 yes
        好友Ai消息 yes
        自定义关键词回复 yes
        管理员公众号消息转发给推送群聊 yes
        查看白名单群聊 yes
        查看黑名单群聊 yes
        查看推送群聊 yes
        查看黑名单公众号 yes
        好友红包消息处理 yes
        好友转账接收 yes 微信版本过低无法使用
        :param wcf:
        """
        self.wcf = wcf
        self.Ad = AiDialogue()
        self.Dms = DbMainServer()
        configData = Cs.returnConfigData()
        # 超级管理员列表
        self.Administrators = configData['Administrators']
        # 给好友发消息关键词
        self.sendMsgKeyWords = configData['adminFunctionWord']['sendMsgWord']
        # Ai锁
        self.aiLock = configData['systemConfig']['aiLock']
        # 转账接收锁
        self.acceptMoneyLock = configData['systemConfig']['acceptMoneyLock']
        # 自动同意好友锁
        self.acceptFriendLock = configData['systemConfig']['acceptFriendLock']
        # 进群关键词字典
        self.roomKeyWords = configData['roomKeyWord']
        # 自定义回复关键词字典
        self.customKeyWords = configData['customKeyWord']
        # 查看白名单群聊关键词
        self.showWhiteRoomKeyWords = configData['adminFunctionWord']['showWhiteRoomWord']
        # 查看黑名单群聊关键词
        self.showBlackRoomKeyWords = configData['adminFunctionWord']['showBlackRoomWord']
        # 查看推送群聊关键词
        self.showPushRoomKeyWords = configData['adminFunctionWord']['showPushRoomWord']
        # 查看黑名单公众号关键词
        self.showBlackGhKeyWords = configData['adminFunctionWord']['showBlackGhWord']
        # 添加好友后自动回复消息
        self.acceptFriendMsg = configData['customMsg']['acceptFriendMsg']

    def mainHandle(self, msg, user_nick_name="user", isChatHistory=False):
        content = msg.content.strip()
        sender = msg.sender
        msgType = msg.type

        if msgType == 1:
            # Ai对话 Ai锁功能 对超管没用
            if self.aiLock or sender in self.Administrators:
                Thread(target=self.getAiMsg, args=(content, sender, user_nick_name, isChatHistory)).start()
        # 好友自动同意处理 暂时没用 老版本微信有用
        if msgType == 37 and self.acceptFriendLock:
            Thread(target=self.acceptFriend, args=(msg,)).start()

    def acceptFriend(self, msg):
        """
        同意好友申请处理
        :return:
        """
        root_xml = ET.fromstring(msg.content.strip())
        wxId = root_xml.attrib["fromusername"]
        op(f'[*]: 接收到新的好友申请, 微信id为: {wxId}')
        v3 = root_xml.attrib["encryptusername"]
        v4 = root_xml.attrib["ticket"]
        scene = int(root_xml.attrib["scene"])
        ret = self.wcf.accept_new_friend(v3=v3, v4=v4, scene=scene)
        acceptSendMsg = self.acceptFriendMsg.replace('\\n', '\n')
        self.wcf.send_text(acceptSendMsg, receiver=wxId)
        if ret:
            op(f'[+]: 好友 {self.wcf.get_info_by_wxid(wxId).get("name")} 已自动通过 !')
        else:
            op(f'[-]: 好友通过失败！！！')

    def acceptMoney(self, msg):
        """
        处理转账消息, 只处理好友转账
        :param msg:
        :return:
        """
        root_xml = ET.fromstring(msg.content.strip())
        title_element = root_xml.find(".//title")
        title = title_element.text if title_element is not None else None
        if '微信转账' == title and msg.sender != self.wcf.self_wxid:
            transCationId = root_xml.find('.//transcationid').text
            transFerid = root_xml.find('.//transferid').text
            if not self.wcf.receive_transfer(wxid=msg.sender, transactionid=transCationId,
                                             transferid=transFerid):
                op(f'[-]: 接收好友转账失败, 可能是版本不支持')

    def forwardRedPacketMsg(self, sender):
        """
        转发红包消息给主人
        :return:
        """
        for administrator in self.Administrators:
            self.wcf.send_text(f'[爱心]接收到好友: {getIdName(self.wcf, sender)} 的红包, 请在手机上接收',
                               receiver=administrator)
        self.wcf.send_text(f'[爱心]已接收到您的红包, 感谢支持', receiver=sender)

    def showBlackGh(self, sender):
        """
        查看黑名单公众号
        :param sender:
        :return:
        """
        blackGhData = self.Dms.showBlackGh()
        sendMsg = '===== 推送群聊列表 =====\n'
        for roomId, roomName in blackGhData.items():
            sendMsg += f'公众号ID: {roomId}\n公众号昵称: {roomName}\n---------------\n'
        if not blackGhData:
            sendMsg = '暂无公众号添加至黑名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showPushRoom(self, sender):
        """
        查看推送群聊
        :param sender:
        :return:
        """
        pushRoomData = self.Dms.showPushRoom()
        sendMsg = '===== 推送群聊列表 =====\n'
        for roomId, roomName in pushRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not pushRoomData:
            sendMsg = '暂无群聊开启推送服务'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showBlackRoom(self, sender):
        """
        查看黑名单群聊 超管有效
        :return:
        """
        blackRoomData = self.Dms.showBlackRoom()
        sendMsg = '===== 黑名单群聊列表 =====\n'
        for roomId, roomName in blackRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not blackRoomData:
            sendMsg = '暂无群聊添加至黑名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showWhiteRoom(self, sender):
        """
        查看白名单群聊 超管有效
        :return:
        """
        whiteRoomData = self.Dms.showWhiteRoom()
        sendMsg = '===== 白名单群聊列表 =====\n'
        for roomId, roomName in whiteRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not whiteRoomData:
            sendMsg = '暂无群聊添加至白名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def forwardGhMsg(self, msgId):
        """
        转发公众号消息到推送群来哦 超管有效
        :param msgId:
        :return:
        """
        pushRoomDicts = self.Dms.showPushRoom()
        for pushRoomId in pushRoomDicts.keys():
            self.wcf.forward_msg(msgId, receiver=pushRoomId)

    def customKeyWordMsg(self, sender, content):
        """
        自定义关键词消息回复
        :param sender:
        :param content:
        :return:
        """
        for keyWord in self.customKeyWords.keys():
            if judgeEqualWord(content, keyWord):
                replyMsgLists = self.customKeyWords.get(keyWord)
                for replyMsg in replyMsgLists:
                    self.wcf.send_text(replyMsg, receiver=sender)

    def keyWordJoinRoom(self, sender, content):
        """
        关键词进群
        :param sender:
        :param content:
        :return:
        """
        for keyWord in self.roomKeyWords.keys():
            if judgeEqualWord(content, keyWord):
                roomLists = self.roomKeyWords.get(keyWord)
                for roomId in roomLists:
                    roomMember = self.wcf.get_chatroom_members(roomId)
                    if len(roomMember) == 500:
                        continue
                    if sender in roomMember.keys():
                        self.wcf.send_text(f'你小子已经进群了, 还想干吗[旺柴]', receiver=sender)
                        break
                    if self.wcf.invite_chatroom_members(roomId, sender):
                        op(f'[+]: 已将 {sender} 拉入群聊【{roomId}】')
                        break
                    else:
                        op(f'[-]: {sender} 拉入群聊【{roomId}】失败 !!!')

    def sendFriendMsg(self, content):
        """
        给好友发消息 只对超管生效
        :param content:
        :return:
        """
        wxId = content.split(' ')[1]
        sendMsg = f'==== [爱心]来自超管的消息[爱心] ====\n\n{content.split(" ")[-1]}\n\n====== [爱心]NGCBot[爱心] ======'
        self.wcf.send_text(sendMsg, receiver=wxId)

    def getAiMsg(self, content, sender, user_nick_name, isChatHistory=False):
        """
        好友Ai对话
        :param content:
        :param sender:
        :return:
        """
        aiMsg = self.Ad.get_eqmaster_Ai(content, user_nick_name, isChatHistory)
        if aiMsg:
            aiMsg_segment = aiMsg.split("\n\n")
            for i in aiMsg_segment:
                i = i.strip()
                if len(i) > 4:
                    self.wcf.send_text(i, receiver=sender)
                    time.sleep(3)
            return
        self.wcf.send_text(f'Ai对话接口出现错误, 请稍后再试 ~~~', receiver=sender)

    def forwardMsgToAdministrators(self, wxId, content):
        """
        好友消息转发给超级管理员
        :param wxId:
        :param content:
        :return:
        """
        forwardMsg = f"= [爱心]收到来自好友的消息[爱心] =\n好友ID: {wxId}\n好友昵称: {getIdName(self.wcf, wxId)}\n好友消息: {content}\n====== [爱心]NGCBot[爱心] ======"
        for administrator in self.Administrators:
            self.wcf.send_text(forwardMsg, receiver=administrator)


if __name__ == '__main__':
    Fmh = FriendMsgHandle(1)
    Fmh.showWhiteRoom()
