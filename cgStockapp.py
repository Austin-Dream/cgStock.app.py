import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# 设置页面配置
st.set_page_config(
    page_title="库存汇总系统",
    page_icon="📊",
    layout="wide"
)

class InventorySummary:
    def __init__(self):
        self.cloud_df = None
        self.cg_df = None
        self.summary_df = None
        # 硬编码的SKU映射表 - CG仓SKU到云仓SKU的映射
        self.cg_to_cloud_mapping = {
            # WS007系列映射
            "WS007-30-KING": "WS007-192-12",
            "WS007-30-QUEEN": "WS007-152-12",
            "WS007-30-FULL": "WS007-137-12",
            "WS007-30-TWIN": "WS007-99-12",
            "WS007-26-KING": "WS007-192-10",
            "WS007-26-QUEEN": "WS007-152-10",
            "WS007-26-FULL": "WS007-137-10",
            "WS007-35-KING": "WS007-192-14",
            "WS007-35-QUEEN": "WS007-152-14",
            "WS007-35-FULL": "WS007-137-14",
            "WS007-35-TWIN": "WS007-99-14",
            
            # WS008系列映射
            "WS008-30-KING": "WS008-192-12",
            "WS008-30-QUEEN": "WS008-152-12",
            "WS008-30-FULL": "WS008-137-12",
            "WS008-30-TWIN": "WS008-99-12",
            "WS008-26-KING": "WS008-192-10",
            "WS008-26-QUEEN": "WS008-152-10",
            "WS008-26-FULL": "WS008-137-10",
            "WS008-35-KING": "WS008-192-14",
            "WS008-35-QUEEN": "WS008-152-14",
            "WS008-35-FULL": "WS008-137-14",
            "WS008-35-TWIN": "WS008-99-14"
        }
        
        # 创建云仓SKU到CG仓SKU的反向映射
        self.cloud_to_cg_mapping = {v: k for k, v in self.cg_to_cloud_mapping.items()}
    
    def load_cloud_inventory(self, cloud_data):
        """加载云仓库存数据"""
        self.cloud_df = cloud_data
        # 清理数据，确保数值列正确
        numeric_columns = ['代发途中', '代发库存', '中转途中', '中转库存', '待处理库存', '10天销量', '30天销量', '库龄(天)', '体积', '库存预警']
        for col in numeric_columns:
            if col in self.cloud_df.columns:
                self.cloud_df[col] = pd.to_numeric(self.cloud_df[col], errors='coerce').fillna(0)
    
    def load_cg_inventory(self, cg_data):
        """加载CG仓库存数据"""
        self.cg_df = cg_data
        # 清理数据
        if 'In Stock' in self.cg_df.columns:
            self.cg_df['In Stock'] = pd.to_numeric(self.cg_df['In Stock'], errors='coerce').fillna(0)
        if 'Available' in self.cg_df.columns:
            self.cg_df['Available'] = pd.to_numeric(self.cg_df['Available'], errors='coerce').fillna(0)
        if 'Order Past 90 Days' in self.cg_df.columns:
            self.cg_df['Order Past 90 Days'] = pd.to_numeric(self.cg_df['Order Past 90 Days'], errors='coerce').fillna(0)
    
    def generate_summary(self):
        """生成库存汇总表"""
        # 获取所有云仓SKU
        cloud_skus = self.cloud_df['Fnsku'].unique() if self.cloud_df is not None else []
        
        # 获取所有映射表中的云仓SKU
        mapped_cloud_skus = list(self.cloud_to_cg_mapping.keys())
        
        # 合并所有云仓SKU
        all_cloud_skus = list(set(list(cloud_skus) + mapped_cloud_skus))
        all_cloud_skus = [sku for sku in all_cloud_skus if pd.notna(sku) and sku != '']
        
        summary_data = []
        
        for cloud_sku in all_cloud_skus:
            # 获取对应的CG仓SKU（平台SKU）
            cg_sku = self.cloud_to_cg_mapping.get(cloud_sku, "")
            
            # 计算云仓库存
            cloud_stock = 0
            cloud_ca_stock = 0
            cloud_ws_stock = 0
            total_cloud_stock = 0
            
            if self.cloud_df is not None:
                cloud_sku_data = self.cloud_df[self.cloud_df['Fnsku'] == cloud_sku]
                if not cloud_sku_data.empty:
                    # 代发库存就是可用库存
                    cloud_stock = cloud_sku_data['代发库存'].sum()
                    # 美西仓库存（X005-CA）
                    ca_stock = cloud_sku_data[cloud_sku_data['仓库名称'] == 'X005-CA']['代发库存'].sum()
                    cloud_ca_stock = ca_stock
                    cloud_ws_stock = cloud_stock - ca_stock  # 其他仓库存
                    total_cloud_stock = cloud_stock
            
            # 计算CG仓库存
            cg_stock = 0
            if self.cg_df is not None and cg_sku:
                # 只计算Castlegate仓库的库存
                cg_data = self.cg_df[
                    (self.cg_df['Part Number'] == cg_sku) & 
                    (self.cg_df['Warehouse Type'] == 'Castlegate')
                ]
                if not cg_data.empty:
                    cg_stock = cg_data['Available'].sum()
            
            # 总库存
            total_stock = total_cloud_stock + cg_stock
            
            summary_data.append({
                'SKU': cloud_sku,  # 使用云仓SKU格式
                '平台sku': cg_sku,  # 使用CG仓SKU格式
                'CALA': cloud_ca_stock,
                'WS': cloud_ws_stock,
                '海外仓总库存': total_cloud_stock,
                'CG库存': cg_stock,
                '总库存': total_stock
            })
        
        self.summary_df = pd.DataFrame(summary_data)
        
        # 添加汇总行
        if not self.summary_df.empty:
            total_row = {
                'SKU': '共计',
                '平台sku': '',
                'CALA': self.summary_df['CALA'].sum(),
                'WS': self.summary_df['WS'].sum(),
                '海外仓总库存': self.summary_df['海外仓总库存'].sum(),
                'CG库存': self.summary_df['CG库存'].sum(),
                '总库存': self.summary_df['总库存'].sum()
            }
            # 将汇总行添加到DataFrame开头
            total_df = pd.DataFrame([total_row])
            self.summary_df = pd.concat([total_df, self.summary_df], ignore_index=True)
        
        return self.summary_df

# Streamlit应用主界面
def main():
    st.title("📊 库存汇总系统")
    st.markdown("上传云仓和CG仓库存数据，自动生成库存汇总表")
    
    # 文件上传区域
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. 上传云仓库存数据")
        cloud_file = st.file_uploader("选择云仓Excel文件", type=["xlsx"], key="cloud")
        
    with col2:
        st.subheader("2. 上传CG仓库存数据")
        cg_file = st.file_uploader("选择CG仓Excel文件", type=["xlsx", "xls"], key="cg")
    
    # 处理按钮
    if st.button("生成库存汇总表", type="primary"):
        if cloud_file is None or cg_file is None:
            st.error("请上传两个数据文件")
            return
        
        # 显示加载状态
        with st.spinner("正在处理数据..."):
            try:
                # 初始化库存汇总器
                inventory = InventorySummary()
                
                # 加载云仓库存
                cloud_data = pd.read_excel(cloud_file, engine='openpyxl')
                inventory.load_cloud_inventory(cloud_data)
                
                # 加载CG仓库存
                # 根据文件类型选择合适的引擎
                if cg_file.name.endswith('.xlsx'):
                    cg_data = pd.read_excel(cg_file, engine='openpyxl')
                else:
                    # 对于.xls文件，使用xlrd引擎
                    try:
                        cg_data = pd.read_excel(cg_file, engine='xlrd')
                    except ImportError:
                        st.error("无法读取.xls文件，请安装xlrd库或上传.xlsx格式文件")
                        return
                
                inventory.load_cg_inventory(cg_data)
                
                # 生成汇总表
                summary = inventory.generate_summary()
                
                # 显示成功消息
                st.success("库存汇总表生成成功！")
                
                # 显示汇总表
                st.subheader("库存汇总表")
                st.dataframe(summary, use_container_width=True)
                
                # 添加下载按钮
                st.subheader("下载汇总表")
                
                # 将DataFrame转换为Excel文件供下载
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary.to_excel(writer, sheet_name='库存汇总', index=False)
                    
                    # 设置列宽
                    worksheet = writer.sheets['库存汇总']
                    column_widths = {
                        'A': 15, 'B': 15, 'C': 8, 'D': 8, 
                        'E': 12, 'F': 8, 'G': 8
                    }
                    for col, width in column_widths.items():
                        worksheet.column_dimensions[col].width = width
                
                output.seek(0)
                
                st.download_button(
                    label="下载Excel文件",
                    data=output,
                    file_name=f"库存汇总表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # 显示统计信息
                st.subheader("库存统计")
                col1, col2, col3, col4 = st.columns(4)
                
                total_stock = summary[summary['SKU'] == '共计']['总库存'].values[0]
                cg_stock = summary[summary['SKU'] == '共计']['CG库存'].values[0]
                cloud_stock = summary[summary['SKU'] == '共计']['海外仓总库存'].values[0]
                sku_count = len(summary) - 1  # 减去汇总行
                
                col1.metric("总库存数量", f"{total_stock:,}")
                col2.metric("CG仓库存", f"{cg_stock:,}")
                col3.metric("云仓库存", f"{cloud_stock:,}")
                col4.metric("SKU数量", f"{sku_count}")
                
            except Exception as e:
                st.error(f"处理数据时出错: {str(e)}")
                st.info("如果遇到xlrd错误，请尝试将CG仓文件转换为.xlsx格式上传")
    
    # 侧边栏信息
    with st.sidebar:
        st.header("使用说明")
        st.markdown("""
        1. 上传云仓库存Excel文件（.xlsx格式）
        2. 上传CG仓库存Excel文件（.xlsx或.xls格式）
        3. 点击"生成库存汇总表"按钮
        4. 查看和下载生成的汇总表
        
        **注意事项：**
        - 云仓文件应包含"Fnsku"和"代发库存"列
        - CG仓文件应包含"Part Number"和"Available"列
        - SKU映射关系已内置在系统中
        - 如果CG仓文件是.xls格式，请确保已安装xlrd库
        """)
        
        st.header("SKU映射说明")
        st.markdown("""
        **SKU列格式：** WS007-192-12 (云仓SKU)
        
        **平台SKU列格式：** WS007-30-KING (CG仓SKU)
        
        系统会自动根据内置映射表进行转换。
        """)
        
        st.header("关于")
        st.markdown("""
        本系统自动整合云仓和CG仓库存数据，
        通过内置的SKU映射表生成统一的库存汇总表。
        
        如有问题，请联系技术支持。
        """)

if __name__ == "__main__":
    main()
