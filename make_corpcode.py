import requests, zipfile, io, xml.etree.ElementTree as ET, json, os

API_KEY = '43290be06d0cc2ce9323fceee47d4d12274e56b0'

print('DART에서 기업코드 목록 다운로드 중...')
res = requests.get(
    'https://opendart.fss.or.kr/api/corpCode.xml',
    params={'crtfc_key': API_KEY},
    timeout=30
)
print(f'다운로드 완료 ({len(res.content)//1024} KB)')

z = zipfile.ZipFile(io.BytesIO(res.content))
xml_data = z.read('CORPCODE.xml').decode('utf-8')
root = ET.fromstring(xml_data)

corps = []
for item in root.findall('list'):
    name = item.findtext('corp_name', '').strip()
    code = item.findtext('corp_code', '').strip()
    stock = item.findtext('stock_code', '').strip()
    if name and code:
        corps.append({'n': name, 'c': code, 's': stock})

print(f'총 {len(corps)}개 기업 파싱 완료')

# 이 스크립트와 같은 폴더에 저장
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corpCode.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(corps, f, ensure_ascii=False, separators=(',', ':'))

size = os.path.getsize(out_path)
print(f'저장 완료: {out_path} ({size//1024} KB)')
