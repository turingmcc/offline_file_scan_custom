import os
import re
import json
import csv
import xlrd
import time
from docx import Document
from datetime import datetime
import pandas as pd  # 使用 pandas 读取 Excel 文件
#import threading
from concurrent.futures import ProcessPoolExecutor
import warnings
warnings.filterwarnings('ignore')

# 工具函数
def column_number_to_letter(col_num):
    # 将列号转换为字母格式（例如，1 -> A）
    letter = ''
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter


def load_config(config_path='config.json'):
    # 加载配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_output_filename(prefix='sensitive_data_report', mode='full'):
    # 生成带有时间戳的输出文件名，并根据模式添加标识
    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{mode}_{current_datetime}.csv"


def generate_log_filename():
    # 生成带有时间戳的日志文件名
    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"scan_files_{current_datetime}.log"


def log_scanned_file(file_path, log_file, status, reason=None):
    # 记录扫描文件的路径和状态到日志文件
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"{status}: {file_path} {('- ' + reason) if reason else ''}\n")


def log_error_to_log_file(log_file, error_message):
    # 错误日志记录到日志文件
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"错误: {error_message}\n")


def log_total_time(total_time, log_file):
    # 记录总扫描时间到日志文件
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"扫描总时间: {total_time:.2f} 秒\n")


def precompile_patterns(patterns):
    # 预编译正则表达式模式以提高性能
    return {key: re.compile(pattern) for key, pattern in patterns.items()}


# 文件扫描函数
def scan_single_file(file_path, patterns, log_file):
    #print(f"扫描文件: {file_path} | 线程ID: {threading.get_ident()}")
    # 扫描单个文件，检测敏感数据
    results = []
    try:
        if file_path.endswith('.csv'):
            results.extend(scan_csv(file_path, patterns, log_file))
        elif file_path.endswith(('.xls', '.xlsx', '.xlsm')):
            results.extend(scan_excel(file_path, patterns, log_file))
        elif file_path.endswith(('.txt', '.log')):
            results.extend(scan_text(file_path, patterns, log_file))
        elif file_path.endswith(('.doc', '.docx')):
            results.extend(scan_word(file_path, patterns, log_file))
    except Exception as e:
        log_error_to_log_file(log_file, f"处理文件 {file_path} 时发生错误: {e}")
    return results


def scan_files(directories, patterns, file_types, log_file, max_depth):
    # 扫描目录下的支持文件类型，生成文件列表
    file_list = []
    for directory in directories:
        for root, _, files in os.walk(directory):
            current_depth = root[len(directory):].count(os.sep)
            if max_depth is not None and current_depth >= max_depth:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                file_path = os.path.abspath(str(file_path))
                if any(file.endswith(ext) for ext in file_types):
                    file_list.append(file_path)
                    log_scanned_file(file_path, log_file, '已扫描')
                    print(f"正在扫描: {file_path}")
                else:
                    log_scanned_file(file_path, log_file, '跳过未指定类型文件')
                    print(f"跳过未指定类型文件: {file_path}")
    return file_list


def scan_csv(file_path, patterns, log_file):
    """
    扫描 CSV 文件，自动尝试多种编码格式读取，检测敏感数据
    参数:
        file_path: CSV 文件路径
        patterns: 预编译的正则表达式模式字典
        log_file: 日志文件路径
    返回:
        results: 检测结果列表，格式为 [文件名, Sheet, 行号, 列号, 敏感类型, 敏感内容]
    """
    results = []
    # 支持的编码列表
    encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'ISO-8859-1', 'latin1']
    # 遍历所有编码尝试解码
    for encoding in encodings:
        try:
            # 尝试用当前编码打开文件
            with open(file_path, mode='r', encoding=encoding) as f:
                reader = csv.reader(f)
                for row_num, row in enumerate(reader, start=1):
                    for col_num, cell in enumerate(row, start=1):
                        # 对每个单元格内容进行正则匹配
                        for key, pattern in patterns.items():
                            if pattern.search(str(cell)):
                                results.append([
                                    file_path,
                                    'N/A',  # CSV 无 Sheet 概念
                                    row_num,
                                    column_number_to_letter(col_num),
                                    key,
                                    cell
                                    # str(cell)[:100]防止超长内容影响可读性
                                ])
                # 成功读取后直接返回结果
                return results
        except UnicodeDecodeError:
            # 编码不匹配，静默尝试下一种编码
            continue
        except csv.Error as e:
            # 记录 CSV 格式错误（如列数不一致）
            log_error_to_log_file(log_file,
                                  f"CSV 解析失败 | 文件: {file_path} | 编码: {encoding} | 错误类型: {type(e).__name__} | 详情: {str(e)}")
            continue
        except Exception as e:
            # 记录其他致命错误（如文件权限问题）
            log_error_to_log_file(log_file,
                                  f"致命错误 | 文件: {file_path} | 编码: {encoding} | 错误类型: {type(e).__name__} | 详情: {str(e)}")
            return results  # 遇到非解码错误，终止尝试

    # 所有编码尝试均失败
    log_error_to_log_file(log_file,
                          f"无法解码文件 | 文件: {file_path} | 已尝试编码: {', '.join(encodings)}")
    return results


def scan_excel(file_path, patterns, log_file):
    # 扫描 Excel 文件
    results = []
    try:
        if file_path.endswith('.xls'):
            # 使用 xlrd 处理旧版 .xls 文件
            book = xlrd.open_workbook(file_path)
            for sheet_name in book.sheet_names():
                sheet = book.sheet_by_name(sheet_name)
                for row_num in range(sheet.nrows):
                    for col_num in range(sheet.ncols):
                        cell = str(sheet.cell_value(row_num, col_num))
                        for key, pattern in patterns.items():
                            if pattern.search(cell):
                                results.append(
                                    [file_path, sheet_name, row_num + 1, column_number_to_letter(col_num + 1), key,
                                     cell])
        else:
            # 使用 pandas 读取新版 .xlsx 和 .xlsm 文件（需显式指定engine）
            dfs = pd.read_excel(file_path, sheet_name=None, dtype=str, engine='openpyxl')  # 读取所有 Sheet
            for sheet_name, df in dfs.items():
                df = df.fillna('')  # 处理空值
                for df_row_num, row in df.iterrows():
                    for col_num, (_, cell_value) in enumerate(row.items(), start=1):
                        cell_str = str(cell_value).strip()
                        # 计算实际Excel行号（假设有标题行）
                        xlsx_row_num = df_row_num + 2
                        for key, pattern in patterns.items():
                            if pattern.search(cell_str):
                                results.append([
                                    file_path,
                                    sheet_name,
                                    xlsx_row_num,  # 修正行号计算
                                    column_number_to_letter(col_num),
                                    key,
                                    cell_str[:100]  # 截断超长内容
                                ])
    except Exception as e:
        log_error_to_log_file(log_file, f"处理 Excel 文件 {file_path} 时发生错误: {e}")
    return results


def scan_text(file_path, patterns, log_file):
    # 扫描文本文件（txt 和 log），尝试多种编码打开文件
    results = []
    encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'ISO-8859-1', 'latin1']  # 支持的编码列表
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                for row_num, line in enumerate(f, start=1):
                    for key, pattern in patterns.items():
                        if pattern.search(line):
                            results.append([file_path, 'N/A', row_num, 'N/A', key, line.strip()])
            # 如果成功读取文件，直接返回结果
            return results
        except UnicodeDecodeError:
            # 如果当前编码失败，尝试下一种编码
            continue
        except Exception as e:
            # 记录其他错误
            log_error_to_log_file(log_file, f"处理文本文件 {file_path} 时发生错误: {e}")
            return results
    # 如果所有编码都失败，记录错误
    log_error_to_log_file(log_file, f"无法解码文件: {file_path}（尝试了所有支持的编码）")
    return results


def scan_word(file_path, patterns, log_file):
    # 扫描 Word 文件（doc 和 docx）
    results = []
    try:
        doc = Document(file_path)
        for paragraph_num, paragraph in enumerate(doc.paragraphs, start=1):
            for key, pattern in patterns.items():
                if pattern.search(paragraph.text):
                    results.append([file_path, 'N/A', paragraph_num, 'N/A', key, paragraph.text.strip()])
    except Exception as e:
        log_error_to_log_file(log_file, f"处理 Word 文件 {file_path} 时发生错误: {e}")
    return results


def save_results(results, output_mode, output_file=None):
    # 将扫描结果保存到 CSV 文件
    if not output_file:
        output_file = generate_output_filename(mode=output_mode)  # 根据输出模式生成文件名

    headers = ['文件名', 'Sheet', '行号', '列号', '敏感类型', '敏感内容']
    if output_mode == 'summary':
        headers.append('统计信息')

    with open(output_file, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(results)


# 主程序入口
def main():
    config = load_config()
    patterns = precompile_patterns(config['patterns'])
    directories = config['directories']
    file_types = config.get('file_types', [])
    max_depth = config.get('max_depth', None)
    threads = config.get('threads', 1)  # 使用配置中的线程数
    output_mode = config.get('output_mode', 'all').lower()  # 新增输出模式配置

    log_file = generate_log_filename()

    start_time = time.time()

    # 生成文件列表
    file_list = scan_files(directories, patterns, file_types, log_file, max_depth)

    # 使用 ProcessPoolExecutor 并发扫描文件
    results = []
    with ProcessPoolExecutor(max_workers=threads) as executor:
        futures = []
        for file_path in file_list:
            # 提交任务到线程池
            future = executor.submit(scan_single_file, file_path, patterns, log_file)
            futures.append(future)
        # 等待所有任务完成并收集结果
        for future in futures:
            results.extend(future.result())

    # 根据输出模式处理结果
    if output_mode == 'summary':
        # 统计每种敏感类型的数量
        type_count = {}
        for item in results:
            sensitive_type = item[4]
            type_count[sensitive_type] = type_count.get(sensitive_type, 0) + 1
        # 生成摘要结果
        seen = set()
        summary_results = []
        for item in results:
            # 使用文件名和敏感类型作为唯一标识
            identifier = (os.path.abspath(item[0]), item[4])
            if identifier not in seen:
                seen.add(identifier)
                # 添加数量统计信息
                item.append(f"出现次数: {type_count[item[4]]}")
                summary_results.append(item)
        results = summary_results

    end_time = time.time()
    total_time = end_time - start_time
    print(f"扫描总时间: {total_time:.2f} 秒")

    log_total_time(total_time, log_file)

    save_results(results, output_mode)


if __name__ == '__main__':
    main()
