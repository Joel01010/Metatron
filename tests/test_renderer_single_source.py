from pathlib import Path

def test_orb_renderer_has_one_canonical_source():
    root=Path(__file__).resolve().parents[1]
    candidates=[p for p in root.rglob('orb-renderer.js') if '.git' not in p.parts]
    assert candidates == [root/'ui'/'orb-renderer.js']
    html=(root/'ui'/'orb.html').read_text(encoding='utf-8')
    assert 'orb-renderer.js' in html
