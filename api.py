from flask import Flask, request, jsonify
from flask_cors import CORS
import main
import html_parser
import os
import tempfile

app = Flask(__name__)
CORS(app)  # 启用CORS支持

@app.route('/api/scrape', methods=['POST'])
def scrape_product():
    """
    爬取1688商品信息的API端点
    请求体格式：
    {
        "url": "https://detail.1688.com/offer/xxx.html"
    }
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({
                'error': '请提供商品URL'
            }), 400

        url = data['url']
        if not url.startswith('https://detail.1688.com/offer/'):
            return jsonify({
                'error': '无效的1688商品URL'
            }), 400

        # 创建临时目录用于存储数据
        with tempfile.TemporaryDirectory() as temp_dir:
            # 设置临时输出文件路径
            output_html = os.path.join(temp_dir, 'output.html')
            
            # 确保data目录存在
            os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
            
            # 爬取商品页面
            main.scrape_1688(url)
            
            # 读取保存的HTML内容
            with open(r"./data/output.html", "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # 解析商品信息
            result = html_parser.run_parser1(html_content, temp_dir)
            if not result:
                result = html_parser.run_parser2(html_content, temp_dir)
            if not result:
                result = html_parser.run_parser3(html_content, temp_dir)

            if result:
                return jsonify({
                    'success': True,
                    'data': result
                })
            else:
                return jsonify({
                    'error': '无法解析商品信息'
                }), 500

    except Exception as e:
        return jsonify({
            'error': f'处理请求时发生错误: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'ok',
        'message': 'API服务正常运行'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 