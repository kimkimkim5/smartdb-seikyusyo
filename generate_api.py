import os
import re
import json
import base64
import fitz  # PyMuPDF
from typing import Dict, Any
import util
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def encode_pdf_page_to_base64(pdf_path: str, page_num: int = 0) -> str:
    """
    PDFの指定ページを画像化し、Base64エンコードして返す関数
    """
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        raise RuntimeError("PDFファイルが空です。")
    
    page = doc[page_num]
    # 解像度を上げる（3x3 = 約216DPI相当）
    mat = fitz.Matrix(3, 3)
    pix = page.get_pixmap(matrix=mat)
    
    # メモリ上の画像をPNGとしてバイト列に変換
    img_bytes = pix.tobytes("png")
    doc.close()
    
    return base64.b64encode(img_bytes).decode("utf-8")

def extract_tax_amounts_via_openai_vision(base64_image: str) -> Dict[str, Any]:
    """
    画像化した請求書をGPT-5 miniに送り、Vision機能で金額を抽出する関数
    """
    system = (
        "あなたは日本の請求書/領収書から金額情報を抽出するアシスタントです。"
        "画像から『税込金額（総支払額）』と『消費税金額』を特定してください。"
        "不明な場合は null にしてください。推測で埋めないでください。"
    )

    user_prompt = """
添付された請求書画像から次を抽出してJSONで返してください。

- total_including_tax: 税込金額（合計・総支払額・請求金額など）
- consumption_tax: 消費税金額（消費税、税額、消費税等）
- evidence: それぞれの根拠となるテキスト（画像内の該当箇所を短く抜粋）

出力は必ず次のJSON形式のみ（余計な文章は禁止）:
{
  "total_including_tax":   "<文字列 or null>",
  "consumption_tax":       "<文字列 or null>",
  "evidence": {
    "total_including_tax": "<根拠行 or null>",
    "consumption_tax":     "<根拠行 or null>"
  }
}
"""

    resp = client.chat.completions.create(
        model="gpt-5-mini",
        # GPT-5 mini/o-seriesではtemperature=0がエラーになるため、省略または1を指定
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            },
        ],
    )

    content = resp.choices[0].message.content.strip()
    # Markdownのコードブロック(```json ... ```)が含まれる場合の除去
    content = re.sub(r"```json\s?|\s?```", "", content)
    
    data = json.loads(content)

    # 正規化（整数化）
    total_raw = data.get("total_including_tax")
    tax_raw =   data.get("consumption_tax")

    return {
        "total_including_tax_raw":         total_raw,
        "consumption_tax_raw":             tax_raw,
        "total_including_tax":             util.normalize_money(total_raw),
        "consumption_tax":                 util.normalize_money(tax_raw),
        "evidence":                        data.get("evidence", {}),
    }

def main(pdf_path: str):
    """
    メイン関数
    """
    # 1. PDFの1ページ目を画像化
    try:
        base64_img = encode_pdf_page_to_base64(pdf_path, page_num=0)
    except Exception as e:
        raise RuntimeError(f"PDFの画像化に失敗しました: {e}")

    # 2. Vision APIで解析
    result = extract_tax_amounts_via_openai_vision(base64_img)
    
    total_including_tax = result["total_including_tax"]
    consumption_tax     = result["consumption_tax"]
    
    try: 
        # 両方が数値（Noneでない）場合のみ計算
        if total_including_tax is not None and consumption_tax is not None:
            total_decluding_tax = total_including_tax - consumption_tax
        else:
            total_decluding_tax = 0
    except TypeError:
        total_decluding_tax = 0
    
    return total_including_tax, consumption_tax, total_decluding_tax
