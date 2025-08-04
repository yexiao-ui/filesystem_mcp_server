# filesystem.py
import os
import copy
import httpx
from asyncio import sleep
from aiofiles import open as aio_open
from aiofiles.os import rename, replace, remove
from pathlib import Path
from uuid import uuid4
import chardet
from mcp.server.fastmcp import FastMCP
import mcp.types as types
import re
import PyPDF2
from spire.doc import *
from spire.doc.common import *
import sys
import json
import argparse
import logging


# 创建MCP服务器实例
mcp = FastMCP(
    name="mcp-server-filemanager",
    version="1.0.0",
    instructions="This is a MCP server for managing several types of files on your own PC."
)

async def validate_path(file_path: str) -> Path:
    """验证并标准化文件路径"""
    path = Path(file_path).absolute()
    # 假设工具只允许操作特定目录，例如F:\Python Project
    if not path.is_relative_to("F:\\Python Project"):
        raise PermissionError("路径超出允许范围")
    logging.info(f"已验证路径: {path}")
    return path


async def read_txt(name: str, arguments: dict) -> list[types.TextContent]:
    """
    读取txt文件内容
    :param file_path: 文件路径
    :return: 文件内容
    """
    try:
        file_path = arguments.get("file_path","")
        with open(file_path, 'rb') as f: raw_data = f.read(1000)
        result = chardet.detect(raw_data)
        file_extension = os.path.splitext(file_path)[1]
        encoding = result['encoding'] if result['confidence'] > 0.5 else 'utf-8'
        with open(file_path, 'r', encoding=encoding) as f:
            text = f.read()

        return [types.TextContent(type="text", text=text)]

    except Exception as e:
        raise Exception(f"读取文件时出错: {e}")


async def read_word_document(name: str, arguments: dict) -> list[types.TextContent]:
    """
    读取word文件内容
    :param file_path: 文件路径
    :return: 文件内容
    """
    try:
        file_path = arguments.get("file_path","")
        # 打开 Word 文档
        document = Document()
        document.LoadFromFile(file_path)
        text = document.GetText()
        document.Close()
        # 遍历文档中的每个段落
        return [types.TextContent(type="text", text=text)]

    except Exception as e:
        raise Exception(f"读取文件时出错: {e}")


async def read_pdf(name: str, arguments: dict) -> list[types.TextContent]:
    """
    读取pdf文件内容
    :param file_path: 文件路径
    :return: 文件内容
    """
    try:
        file_path = arguments.get("file_path","")
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            contents_list = []
            for page in pdf_reader.pages:
                content = page.extract_text()
                contents_list.append(content)
            text = "\n".join(contents_list)
        return [types.TextContent(type="text", text=text)]
    except Exception as e:
        raise Exception(f"读取文件时出错: {e}")

# pdf_path = "D:\\2022级海南智科江昊原申请材料合集\\resume（English version）.pdf"
# pdf = read_pdf(pdf_path)
# print(pdf)


async def list_directories(name: str, arguments: dict) -> list[types.TextContent]:
    """
    读取目录下的所有文件
    :param directory_path: 目录路径
    :return: 文件列表
    """
    try:
        directory_path = arguments.get("directory_path", "")
        file_list = []
        file_types = [".txt", ".docx", ".pdf"]
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_extension = os.path.splitext(file)[1]
                if file_extension in file_types:
                    file_path = os.path.join(root, file)
                    file_list.append(file_path)
        text = "\n".join(file_list)
        return [types.TextContent(type="text", text=text)]
    except Exception as e:
        raise Exception(f"读取目录时出错: {e}")


async def write_file(name: str, arguments: dict) -> list[types.TextContent]:
    """
    写入文件
    :param file_name:文件名称，包括文件扩展名
    :param file_path:文件存入的目录路径
    :param content: 文件内容
    :return:写入成功或失败
    """
    try:
        # Step 1: 从参数中提取信息
        file_name = arguments["file_name"]
        file_path = arguments["file_path"]
        content = arguments["content"]

        # Step 2: 验证路径权限
        validated_path = await validate_path(file_path)

        # Step 3: 原子写入逻辑
        temp_file = f"{validated_path}.{uuid4().hex}.tmp"

        # 创建临时文件
        async with aio_open(temp_file, "w", encoding="utf-8") as f:
            await f.write(content)
        logging.info(f"已创建临时文件: {temp_file}")

        final_path = f"{validated_path}\\{file_name}"

        # Step 4: 替换原始文件（原子操作）
        if os.path.exists(final_path):
            await replace(temp_file, final_path)
        else:
            await rename(temp_file, final_path)
        logging.info(f"成功替换文件: {final_path}")

        return [types.TextContent(type="text", text="写入成功")]

    except KeyError as e:
        logging.error(f"缺少必要参数: {str(e)}")
        return [types.TextContent(type="text", text="缺少必要参数")]
    except PermissionError as e:
        logging.error(f"权限错误: {str(e)}")
        return [types.TextContent(type="text", text="权限错误")]
    except Exception as e:
        # 错误处理：删除残留临时文件
        try:
            if os.path.exists(temp_file):
                await remove(temp_file)
        except:
            pass
        logging.error(f"写入失败: {str(e)}")
        return [types.TextContent(type="text", text="写入失败")]
    

async def list_tools() -> list[types.Tool]:
    """
    列出所有可用的工具
    :param: None
    :return: list (types.Tool): 包含了所有可用的工具, 每个工具都包含了名称、描述、输入schema三个属性.
    """
    tools = [
        types.TextContent(type="text", text="list_directories"),
        types.TextContent(type="text", text="read_txt"),
        types.TextContent(type="text", text="read_word_document"),
        types.TextContent(type="text", text="read_pdf"),
        types.TextContent(type="text", text="write_file"),
        types.TextContent(type="text", text="list_tools")
    ]
    return [
        types.Tool(
            name="list_directories",
            description="列出指定目录下的所有文件",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "需要查询的目录路径"
                    }
                },
                "required": ["directory_path"]
            }
        ),
        types.Tool(
            name="read_txt",
            description="读取txt文件内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "需要读取的txt文件路径"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="read_word_document",
            description="读取word文件内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "需要读取的word文件路径"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="read_pdf",
            description="读取pdf文件内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "需要读取的pdf文件路径"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="write_file",
            description="在指定目录下写入文件",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "文件名称，包括文件扩展名"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "文件存入的目录路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容"
                    }
                },
                "required": ["file_name", "file_path", "content"]
            }
        ),
    ]


async def dispatch(name: str, args: dict) -> list[types.TextContent]:
    """
    根据工具名称和参数调用相应的工具
    :param name: 工具名称，可选值为："list_directories", "read_txt", "read_word_document", "read_pdf"
    :param args: 工具参数
    :return: 工具返回的结果
    """
    match name:
        case "list_directories":
            return await list_directories(name, args)
        case "read_txt":
            return await read_txt(name, args)
        case "read_word_document":
            return await read_word_document(name, args)
        case "read_pdf":
            return await read_pdf(name, args)
        case "write_file":
            return await write_file(name, args)
        case _:
            raise Exception(f"未知的工具：{name} ")




# 注册list_tools方法
mcp._mcp_server.list_tools()(list_tools)
# 注册dispatch方法
mcp._mcp_server.call_tool()(dispatch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mcp-server-filemanager")
    parser.add_argument("allowed_dirs", nargs="+", help="List of allowed directories for file operations")
    args = parser.parse_args()

    allowed_directories = [os.path.abspath(dir_path) for dir_path in args.allowed_dirs]

    mcp.run()

