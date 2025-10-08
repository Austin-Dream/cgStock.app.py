import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import base64
import traceback
from datetime import datetime

# 检查必要依赖
try:
    import openpyxl
except ImportError:
    st.error("缺少必要的依赖包 'openpyxl'。请安装该包：pip install openpyxl")
    st.stop()

# 设置页面配置
st.set_page_config(
    page_title="赛狐文件和WF对接转化器",
    page_icon="📊",
    layout="wide"
)

# 固定的SKU映射表
SKU_MAPPING = {
    "WS007-137-10": "WS007-26-FULL",
    "WS007-137-12": "WS007-30-FULL",
    "WS007-137-14": "WS007-35-FULL",
    "WS007-152-10": "WS007-26-QUEEN",
    "WS007-152-12": "WS007-30-QUEEN",
    "WS007-152-14": "WS007-35-QUEEN",
    "WS007-192-10": "WS007-26-KING",
    "WS007-192-12": "WS007-30-KING",
    "WS007-192-14": "WS007-35-KING",
    "WS007-99-12": "WS007-30-TWIN",
    "WS007-99-14": "WS007-35-TWIN",
    "WS008-137-10": "WS008-26-FULL",
    "WS008-137-12": "WS008-30-FULL",
    "WS008-137-14": "WS008-35-FULL",
    "WS008-152-10": "WS008-26-QUEEN",
    "WS008-152-12": "WS008-30-QUEEN",
    "WS008-152-14": "WS008-35-QUEEN",
    "WS008-192-10": "WS008-26-KING",
    "WS008-192-12": "WS008-30-KING",
    "WS008-192-14": "WS008-35-KING",
    "WS008-99-12": "WS008-30-TWIN",
    "WS008-99-14": "WS008-35-TWIN"
}

def log_error(error_msg):
    """记录错误到日志文件"""
    try:
        with open("error_log.txt", "a", encoding='utf-8') as f:
            f.write(f"{pd.Timestamp.now()}: {error_msg}\n")
    except Exception:
        pass  # 如果日志写入失败，不中断程序

def reverse_sku_mapping(original_sku):
    """反向映射SKU：从值找键"""
    try:
        return SKU_MAPPING.get(original_sku, original_sku)
    except Exception as e:
        log_error(f"SKU映射错误: {str(e)}")
        return original_sku

def format_phone_number(phone_str):
    """格式化电话号码"""
    try:
        if pd.isna(phone_str) or phone_str == "":
            return ""
        
        phone_digits = re.sub(r'\D', '', str(phone_str))
        
        if len(phone_digits) == 10:
            return f"+1 {phone_digits[:3]}-{phone_digits[3:6]}-{phone_digits[6:]}"
        else:
            return str(phone_str)
    except Exception as e:
        log_error(f"电话号码格式化错误: {str(e)}")
        return str(phone_str)

def split_address(address1, address2, door_number, max_length=35):
    """拆分地址"""
    try:
        parts = []
        for addr in [address1, address2, door_number]:
            if pd.notna(addr) and str(addr).strip() and str(addr).strip() != "nan":
                parts.append(str(addr).strip())
        
        if not parts:
            return "", ""
            
        full_address = " ".join(parts)
        
        if len(full_address) <= max_length:
            return full_address, ""
        
        split_index = max_length
        while split_index > 0 and full_address[split_index] != ' ':
            split_index -= 1
        
        if split_index == 0:
            split_index = max_length
        
        address_line1 = full_address[:split_index].strip()
        address_line2 = full_address[split_index:].strip()
        
        return address_line1, address_line2
    except Exception as e:
        log_error(f"地址拆分错误: {str(e)}")
        return str(address1), ""

def process_excel_data(df):
    """处理在赛狐平台下载的数据"""
    new_rows = []
    
    try:
        for _, row in df.iterrows():
            # 检查必要的列是否存在
            if 'SKU' not in row or 'SKU数量' not in row:
                continue
                
            if pd.isna(row.get('SKU')) or row.get('SKU数量', 0) == 0:
                continue
                
            order_number = row.get('订单号', '')
            quantity = int(float(row.get('SKU数量', 1)))  # 处理可能的浮点数
            
            for i in range(quantity):
                new_row = {}
                suffix = f"-{i+1}" if quantity > 1 else ""
                
                new_row['Retailer ID'] = ''
                new_row['Retailer PO Number'] = f"{order_number}{suffix}"
                new_row['Retailer Order Number'] = f"{order_number}{suffix}"
                new_row['Recipient Order Number'] = ''
                new_row['Part Number'] = reverse_sku_mapping(row.get('SKU', ''))
                new_row['Quantity'] = 1
                new_row['Fulfillment Warehouse ID'] = ''
                new_row['Shipping Account Number'] = ''
                new_row['SCAC Code'] = ''
                new_row['Ship Speed'] = ''
                new_row['Shipping Name'] = row.get('收件人', '')
                
                addr1, addr2 = split_address(
                    row.get('地址1', ''),
                    row.get('地址2', ''),
                    row.get('门牌号', '')
                )
                new_row['Shipping Address 1'] = addr1
                new_row['Shipping Address 2'] = addr2
                
                new_row['Shipping City'] = row.get('城市', '')
                new_row['Shipping State'] = row.get('州/省', '')
                new_row['Shipping Postal Code'] = row.get('邮编', '')
                new_row['Shipping Country'] = 'US'
                new_row['Shipping Phone Number'] = format_phone_number(row.get('电话', ''))
                new_row['Shipping Email'] = 'tpcfjjyxgs@163.com'
                
                new_rows.append(new_row)
                
    except Exception as e:
        log_error(f"数据处理错误: {str(e)}")
        st.error(f"数据处理错误: {str(e)}")
    
    return pd.DataFrame(new_rows)

def get_download_link(df, filename):
    """生成下载链接"""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        processed_data = output.getvalue()
        b64 = base64.b64encode(processed_data).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">点击下载处理后的文件</a>'
        return href
    except Exception as e:
        st.error(f"生成下载链接时出错: {str(e)}")
        return ""

def main():
    """主函数"""
    # 标题和说明
    st.title("赛狐文件和WF对接转化器")
    st.markdown("---")
    
    st.markdown("""
    ### 使用说明
    1. 上传从赛狐平台下载的Excel文件
    2. 系统将自动处理数据并生成适用于WF系统的格式
    3. 处理完成后，下载生成的文件
    
    **注意：** 此工具仅适用于赛狐和WF多渠道对接
    """)
    
    # 文件上传区域
    st.markdown("### 上传文件")
    uploaded_file = st.file_uploader("选择要处理的Excel文件", type=["xlsx"])
    
    if uploaded_file is not None:
        try:
            # 读取文件
            st.info("正在读取文件...")
            df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.success(f"成功读取文件，共 {len(df)} 行数据")
            
            # 显示原始数据预览
            with st.expander("查看原始数据预览"):
                st.dataframe(df.head())
            
            # 处理数据
            st.info("正在处理数据...")
            processed_df = process_excel_data(df)
            
            if processed_df.empty:
                st.error("处理完成，但没有生成有效数据，请检查原始文件格式")
            else:
                st.success(f"处理完成，生成 {len(processed_df)} 行数据")
                
                # 显示处理后的数据预览
                with st.expander("查看处理后的数据预览"):
                    st.dataframe(processed_df.head())
                
                # 生成下载链接
                original_filename = uploaded_file.name
                base_name = original_filename.split('.')[0]
                download_filename = f"{base_name}_处理结果.xlsx"
                
                st.markdown("### 下载处理结果")
                st.markdown(get_download_link(processed_df, download_filename), unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"处理出错: {str(e)}")
            st.code(traceback.format_exc())
            log_error(f"处理出错: {str(e)}\n{traceback.format_exc()}")
    
    # 添加页脚
    st.markdown("---")
    st.markdown("如有问题，请检查错误日志文件或联系开发人员")

if __name__ == "__main__":
    main()
