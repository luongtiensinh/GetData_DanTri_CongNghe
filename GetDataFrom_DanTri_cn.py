import requests
from bs4 import BeautifulSoup
import csv
import os
import schedule
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import shutil

# Cấu hình
BASE_URL = "https://dantri.com.vn/"
CATEGORY = "cong-nghe"
CATEGORY_NAME = "Công nghệ"
MAX_PAGES = 10  # Số trang tối đa để thu thập
OUTPUT_FILE = "dantri_congnghe.csv"
IMAGE_FOLDER = "dantri_images"  # Thư mục lưu hình ảnh
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

headers = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Tạo thư mục lưu hình ảnh nếu chưa tồn tại
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def download_image(image_url, article_title):
    """Tải hình ảnh và lưu vào thư mục cục bộ"""
    if not image_url:
        return ""
    
    try:
        # Tạo tên file an toàn từ tiêu đề bài viết
        safe_title = "".join([c if c.isalnum() else "_" for c in article_title])
        safe_title = safe_title[:50]  # Giới hạn độ dài tên file
        
        # Lấy phần mở rộng từ URL
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        extension = os.path.splitext(path)[1]
        if not extension:
            extension = ".jpg"  # Mặc định là jpg nếu không tìm thấy phần mở rộng
        
        # Tạo tên file duy nhất
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{safe_title}_{timestamp}{extension}"
        local_path = os.path.join(IMAGE_FOLDER, filename)
        
        # Tải hình ảnh
        response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        
        # Lưu hình ảnh vào file
        with open(local_path, 'wb') as file:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, file)
        
        print(f"Đã tải hình ảnh: {local_path}")
        return local_path
    
    except Exception as e:
        print(f"Lỗi khi tải hình ảnh từ {image_url}: {str(e)}")
        return ""

def get_article_details(article_url):
    try:
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Lấy tiêu đề
        title_tag = soup.select_one("h1.title-page")
        title = title_tag.get_text(strip=True) if title_tag else "Không có tiêu đề"

        # Lấy mô tả
        description_tag = soup.select_one("div.singular-sapo")
        description = description_tag.get_text(strip=True) if description_tag else "Không có mô tả"

        # Lấy nội dung
        content_div = soup.select_one("div.singular-content")
        if content_div:
            paragraphs = [p.get_text(strip=True) for p in content_div.find_all("p")]
            content = "\n".join([p for p in paragraphs if p])
        else:
            content = "Không có nội dung"

        # Lấy hình ảnh - Sử dụng nhiều selector để tìm ảnh chính
        image_url = ""
        
        # Thử nhiều cách khác nhau để lấy hình ảnh
        # 1. Ảnh từ thẻ figure đầu tiên (thường là ảnh chính)
        figure_img = soup.select_one("figure.singular-image img, figure.e-img img")
        if figure_img:
            # Ưu tiên lấy data-src nếu có
            if 'data-src' in figure_img.attrs:
                image_url = figure_img['data-src']
            # Sau đó là srcset
            elif 'srcset' in figure_img.attrs:
                srcset = figure_img['srcset']
                parts = srcset.split(',')
                if parts:
                    # Lấy URL cuối cùng trong srcset (thường là bản 2x chất lượng cao)
                    image_url = parts[-1].strip().split()[0]
            # Cuối cùng là src
            elif 'src' in figure_img.attrs:
                image_url = figure_img['src']
        
        # 2. Nếu không tìm thấy, thử tìm trong phần nội dung
        if not image_url:
            content_img = soup.select_one("div.singular-content img, div.article-content img")
            if content_img:
                if 'data-src' in content_img.attrs:
                    image_url = content_img['data-src']
                elif 'srcset' in content_img.attrs:
                    srcset = content_img['srcset']
                    parts = srcset.split(',')
                    if parts:
                        image_url = parts[-1].strip().split()[0]
                elif 'src' in content_img.attrs:
                    image_url = content_img['src']
        
        # 3. Tìm tất cả các ảnh và lấy ảnh đầu tiên
        if not image_url:
            all_imgs = soup.select("img[src], img[data-src]")
            for img in all_imgs:
                if 'data-src' in img.attrs:
                    image_url = img['data-src']
                    break
                elif 'src' in img.attrs:
                    image_url = img['src']
                    break
        
        # Đảm bảo URL hình ảnh là URL đầy đủ
        if image_url and not image_url.startswith(('http://', 'https://')):
            image_url = urljoin(BASE_URL, image_url)

        # In ra thông tin debug
        print(f"- Tiêu đề: {title}")
        print(f"- Hình ảnh URL: {image_url}")
        
        # Tải hình ảnh về máy
        local_image_path = download_image(image_url, title) if image_url else ""

        return {
            'title': title,
            'description': description,
            'image_url': image_url,  # URL hình ảnh trực tuyến
            'local_image': local_image_path,  # Đường dẫn hình ảnh cục bộ
            'content': content,
            'article_url': article_url,
            'scraped_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"Lỗi khi lấy bài viết {article_url}: {str(e)}")
        return None


def scrape_dantri_tech():
    """Thu thập tin tức công nghệ từ Dantri"""
    all_articles = []
    
    for page in range(1, MAX_PAGES + 1):
        # Tạo URL cho từng trang
        if page == 1:
            url = urljoin(BASE_URL, f"{CATEGORY}.htm")
        else:
            url = urljoin(BASE_URL, f"{CATEGORY}/trang-{page}.htm")
        
        print(f"Đang thu thập trang {page}: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Tìm tất cả các bài viết trên trang
            # Thử nhiều selector để phù hợp với cấu trúc trang
            articles = soup.select("article.article-item, div.article, div.news-item")
            
            if not articles:
                print(f"Không tìm thấy bài viết nào trên trang {page}")
                break
            
            print(f"Tìm thấy {len(articles)} bài viết trên trang {page}")
            
            for article in articles:
                link = article.select_one("a[href]")
                if link:
                    article_url = urljoin(BASE_URL, link['href'])
                    print(f"Đang thu thập bài viết: {article_url}")
                    article_data = get_article_details(article_url)
                    if article_data:
                        article_data['category'] = CATEGORY_NAME
                        all_articles.append(article_data)
                        print(f"Đã thu thập: {article_data['title']}")
            
            # Kiểm tra nếu có nút trang tiếp theo
            next_page = soup.select_one("a.next, a.page-next")
            if not next_page:
                print("Không tìm thấy trang tiếp theo, dừng lại")
                break
                
        except Exception as e:
            print(f"Lỗi khi thu thập trang {page}: {str(e)}")
            continue
    
    return all_articles

def save_to_csv(data, filename):
    """Lưu dữ liệu vào file CSV"""
    if not data:
        print("Không có dữ liệu để lưu")
        return
    
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['category', 'title', 'description', 'image_url', 'local_image', 'content', 'article_url', 'scraped_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerows(data)
    
    print(f"Đã lưu {len(data)} bài viết vào {filename}")

def create_html_gallery(data):
    """Tạo một trang HTML hiển thị các bài viết với hình ảnh"""
    html_file = "dantri_gallery.html"
    
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bộ sưu tập tin tức Dantri</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .article {
                background-color: white;
                margin-bottom: 20px;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                display: flex;
            }
            .article-image {
                flex: 0 0 200px;
                margin-right: 20px;
            }
            .article-image img {
                max-width: 100%;
                height: auto;
                border-radius: 5px;
            }
            .article-content {
                flex: 1;
            }
            h1 {
                color: #333;
                margin-top: 0;
            }
            h2 {
                margin-top: 0;
                margin-bottom: 10px;
            }
            p {
                color: #666;
                line-height: 1.5;
            }
            .date {
                color: #999;
                font-size: 0.8em;
                margin-top: 10px;
            }
            a {
                color: #0066cc;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            .description {
                font-weight: bold;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Bộ sưu tập tin tức Dantri - Công nghệ</h1>
    """
    
    for article in data:
        html_content += f"""
            <div class="article">
                <div class="article-image">
                    <img src="{article['local_image'] or 'no_image.png'}" alt="{article['title']}">
                </div>
                <div class="article-content">
                    <h2><a href="{article['article_url']}" target="_blank">{article['title']}</a></h2>
                    <p class="description">{article['description']}</p>
                    <p class="date">Thời gian thu thập: {article['scraped_time']}</p>
                </div>
            </div>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Đã tạo gallery HTML: {html_file}")

def daily_scraping_job():
    """Công việc thu thập hàng ngày"""
    print(f"\n=== Bắt đầu thu thập dữ liệu lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    articles = scrape_dantri_tech()
    
    if articles:
        save_to_csv(articles, OUTPUT_FILE)
        create_html_gallery(articles)  # Tạo gallery HTML
    else:
        print("Không thu thập được bài viết nào")
    
    print(f"=== Hoàn thành lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

def main():
    # Tạo file CSV nếu chưa tồn tại
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'category', 'title', 'description', 'image_url', 'local_image', 
                'content', 'article_url', 'scraped_time'
            ])
            writer.writeheader()
    
    # Lên lịch chạy hàng ngày lúc 6h sáng
    schedule.every().day.at("06:00").do(daily_scraping_job)
    
    # Chạy ngay lần đầu để có dữ liệu
    print("Chạy thu thập dữ liệu ngay lần đầu...")
    daily_scraping_job()
    
    print("Đã thiết lập lịch chạy hàng ngày lúc 6:00 sáng. Đang chờ...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Kiểm tra mỗi phút

if __name__ == "__main__":
    main()