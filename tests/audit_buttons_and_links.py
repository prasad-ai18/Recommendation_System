import re
from pathlib import Path

def audit():
    html = Path('frontend/index.html').read_text(encoding='utf-8')
    js = Path('frontend/js/app.js').read_text(encoding='utf-8')
    
    # Extract all button tags and their IDs/classes/data attributes
    buttons = re.findall(r'<button\s+([^>]+)>', html)
    print(f"Total <button> tags in HTML: {len(buttons)}")
    
    for idx, b in enumerate(buttons, 1):
        id_match = re.search(r'id=["\']([^"\']+)["\']', b)
        cls_match = re.search(r'class=["\']([^"\']+)["\']', b)
        tab_match = re.search(r'data-tab=["\']([^"\']+)["\']', b)
        model_match = re.search(r'data-model=["\']([^"\']+)["\']', b)
        
        btn_id = id_match.group(1) if id_match else None
        btn_cls = cls_match.group(1) if cls_match else None
        
        # Check if button is referenced in JS
        in_js = False
        if btn_id and (f"'{btn_id}'" in js or f'"{btn_id}"' in js or f'#{btn_id}' in js):
            in_js = True
        elif btn_cls:
            for c in btn_cls.split():
                if f"'{c}'" in js or f'"{c}"' in js or f'.{c}' in js:
                    in_js = True
                    break
                    
        print(f"[{'PASS' if in_js else 'WARN'}] Button {idx}: id={btn_id} class={btn_cls} (data-tab={tab_match.group(1) if tab_match else None}, data-model={model_match.group(1) if model_match else None})")

if __name__ == '__main__':
    audit()
