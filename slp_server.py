import time
import socket
import json
import os.path
import base64
import uuid
import threading
import traceback


from enum import IntEnum
from byte_utils import *
from server_logger import ServerLogger
from concurrent.futures import ThreadPoolExecutor

logger = ServerLogger()


class REQUEST(IntEnum):
    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    TRANSFER = 3
    UNKNOWN = 4

class SlpServer:
    def __init__(self,config):
        self.config = config
        self.motd = self.create_motd(config)
        self.is_loop = False
        logger.info("SLP服务器初始化完成")

    @staticmethod
    def create_motd(config):
        logger.info("创建motd")
        #创建motd
        motd = {
            "version": {"name": config["version_text"], "protocol": config["protocol"]},
            "players": {"max": len(config["samples"]), "online": len(config["samples"]), "sample": [{"name": sample, "id": str(uuid.uuid4())} for sample in config["samples"]]},
            "description": {"text": config["motd"]}
        }

        if not os.path.exists(config["server_icon"]):
            logger.warning("未找到服务器图标，默认为空")
        #不添加motd["favicon"]即可（此为可选项）
        else:
            with open(config["server_icon"], 'rb') as image:
                motd["favicon"] = "data:image/png;base64," + base64.b64encode(image.read()).decode()

        return json.dumps(motd)


    def start(self,wait=False,name=None,max_threads=10):
        if self.is_loop:
            logger.info("SLP服务器已启动，请勿再次启动")
            return None

        #设置启动标签
        self.is_loop = True
        logger.info("SLP服务器启动中")


        if wait:
            self.loop(max_threads)
            return
        else:
            thread = threading.Thread(target=self.loop, args=(max_threads,), name=name)
            thread.start()
            return thread
        

    def stop(self):
        if not self.is_loop:
            logger.info("SLP服务器已是关闭状态")
            return

        self.is_loop = False
        logger.info("正在关闭SLP服务器")

    def loop(self,max_threads=10):
        logger.info("SLP服务器循环已启动")
        #FS创建部分
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            server_socket.bind((self.config["ip"], self.config["port"]))
            server_socket.settimeout(None)  # 无限等待
        except Exception as e:
            logger.error(f"SLP服务器启动失败: {traceback.format_exc()}")
            server_socket.close()
            server_socket = None

        # FS监听部分
        if server_socket is not None:
            try:
                executor = ThreadPoolExecutor(max_workers=max_threads)
                server_socket.listen(5)  # 允许5个挂起的链接
                logger.info(f"SLP服务器启动成功，在[{self.config["ip"]}:{self.config["port"]}]监听")
                while self.is_loop:
                    client_socket, client_address = server_socket.accept()
                    logger.info(f"收到来自{client_address[0]}:{client_address[1]}的连接")
                    executor.submit(self.handle_socket, client_socket)  # 提交到线程池
            except Exception as e:
                logger.error(f"发生其它错误: {traceback.format_exc()}")
            except KeyboardInterrupt:
                logger.warn("收到键盘中断，正在停止SLP服务器")
                executor.shutdown(wait=True)
            finally:
                server_socket.close()
                server_socket = None
                self.is_loop = False#强制设置为False

        logger.info("SLP服务器已退出")

    # https://minecraft.wiki/w/Java_Edition_protocol#Handshaking
    # https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Server_List_Ping#1.6
    # https://minecraft.wiki/w/Java_Edition_protocol#Login_Start
    # https://minecraft.wiki/w/Minecraft_Wiki:Projects/wiki.vg_merge/Server_List_Ping#Current_(1.7+)
    # https://minecraft.wiki/w/Java_Edition_protocol#Pong_Response_(status)

    '''
        流程：
        客户端发送握手包，与服务器进行握手
        然后在任何其他请求之前，发送binding包绑定	
        服务器再进行回复
    '''

    def handle_socket(self,client_socket):
        try:
            status = REQUEST.HANDSHAKING
            while True:
                try:
                    head = read_exactly(client_socket,1,timeout=5)[0]
                    logger.info(f"收到数据：[1]>[{hex(head)}]")
    
                    #处理特殊数据头
                    if head == 0xFE:  # 1.6兼容协议，FE开头，强制匹配识别
                        self.handle_head(head,client_socket,status)
                        return#处理完成离开
                    #否则继续
    
                    logger.info("识别为length，继续接收")
                    #为varint长度
                    length = head
                    if (length & 0x80) == 0x80:
                        for j in range(1,6):
                            if j >= 5:
                                raise IOError("Insufficient data for varint")
                            byte_in = read_exactly(client_socket, 1, timeout=5)[0]
                            length |= (byte_in & 0x7F) << (j * 7)
                            if (byte_in & 0x80) != 0x80:
                                break
    
                    logger.info(f"剩余数据长度：[{length}]")
                    #正常数据，数据头解释为长度，继续接收
                    data = BytesReader(read_exactly(client_socket, length, timeout=5))
                    logger.info(f"收到数据：[{data.len()}]>[{format_hex(data.getdata())}]")
    
                    #通过包id处理数据
                    packet_id = data.read_byte()
                    if packet_id == 0x00:
                        if status == REQUEST.HANDSHAKING:#第一个封包
                            logger.info("识别为handshaking")
                            status = self.handle_handshaking(data)#转换到下一个状态
                            continue#重试
                        elif status == REQUEST.LOGIN:  #登录请求(玩家名，0x01，接着是uuid)
                            logger.info("识别为login")
                            self.handle_login(client_socket, data, status)
                            return
                        elif status == REQUEST.STATUS:
                            logger.info("识别为binding")
                            if length == 1:#长度为1：0x01 0x00 为binding包
                                self.handle_binding(client_socket,status)
                            else:
                                logger.warn("binding长度错误")
                            return
                        elif status == REQUEST.UNKNOWN:#未知请求则跳出断开连接
                            logger.warn("识别为unknown")
                            return
                        else:
                            return
                    elif packet_id == 0x01:
                        logger.info("识别为ping")
                        self.handle_ping(client_socket, data)
                        return
                    else:
                        logger.warning("识别为未知数据")
                        return
                except TypeError as e:
                    logger.warning("收到了无效数据（类型错误）")
                    logger.warning(f'error file:\"{e.__traceback__.tb_frame.f_globals["__file__"]}\" line:{e.__traceback__.tb_lineno}')
                    return
                except IndexError as e:
                    logger.warning("收到了无效数据（索引溢出）")
                    logger.warning(f'error file:\"{e.__traceback__.tb_frame.f_globals["__file__"]}\" line:{e.__traceback__.tb_lineno}')
                    return
                except ConnectionError:
                    logger.warning("客户端提前断开连接")
                    return
                except socket.timeout:
                    logger.debug("连接超时")#此处超时处理read_exactly
                    return
                except Exception as e:
                    logger.error(f"发生其它错误: {traceback.format_exc()}")
                    return
        finally:
            #关闭退出
            client_socket.close()
            client_socket = None
            logger.info("断开链接")
        


    @staticmethod
    def handle_handshaking(data):
        version = data.read_varint()
        server_ip = data.read_str()
        # 转义特殊字符
        server_ip = (server_ip
                     .replace('\x00', '\\0')
                     .replace("\r", "\\r")
                     .replace("\t", "\\t")
                     .replace("\n", "\\n"))
        port = data.read_ushort()
        state = data.read_byte()
        logger.info(f"数据解析：version:[{version}], ip:[{server_ip}], port:[{port}], state:[{hex(state)}]")
        if state == 0x01:  # Status
            logger.info("下一个为状态请求")
            return REQUEST.STATUS
        elif state == 0x02:  # Login
            logger.info("下一个为登录请求")
            return REQUEST.LOGIN
        elif state == 0x03:  # Transfer
            logger.info("下一个为转移请求")
            return REQUEST.TRANSFER
        else:# Unknown
            logger.info("下一个为未知请求")
            return REQUEST.UNKNOWN

    #返回值代表是否处理完成
    @staticmethod
    def handle_head(head,client_socket,status):
        next2 = read_exactly(client_socket, 2, timeout=5)
        logger.info(f"收到数据：[2]>[{format_hex(next2)}]")
        if next2[0] != 0x01 or next2[1] != 0xFA:# 确认后两个是 01和fa
            logger.warning("收到了意外的数据包")
        else:
            logger.info("识别为1.6-ping")
            logger.info("发送空响应")
            # 以踢出数据包响应客户端，长度直接设为0，不给出任何信息
            client_socket.sendall(bytes([0xFF, 0x00, 0x00]))

    def handle_binding(self,client_socket,status):
        logger.info("发送motd")
        write_str_response(client_socket, 0x00, self.motd)  # 发送motd

    def handle_login(self, client_socket,data,status):
        player_name = data.read_str()
        rbyte = data.read_byte()
        uuid = data.read_uuid()
        logger.info(f"数据解析：player_name[{player_name}], rbyte[{rbyte}], uuid:[{uuid}]")
        logger.info("发送kick message")
        write_str_response(client_socket, 0x00, json.dumps({"text": self.config["kick_message"]}))

    @staticmethod
    def handle_ping(client_socket,data):
        response = bytearray()
        write_varint(response, 9)#长度9
        write_varint(response, 0x01)#packet_id
        response.append(data.read_long())
        logger.info("发送pong响应")
        client_socket.sendall(response)#返回pong包

