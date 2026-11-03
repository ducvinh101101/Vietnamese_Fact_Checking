import os
import sys
import win32com.client
import fitz

def main():
    pptx_path = os.path.abspath('docs/SLIDE_BAO_CAO_DE_TAI.pptx')
    pdf_path = os.path.abspath('docs/SLIDE_BAO_CAO_DE_TAI.pdf')
    out_dir = os.path.abspath('scratch/slides_v7')
    os.makedirs(out_dir, exist_ok=True)

    powerpoint = win32com.client.Dispatch('PowerPoint.Application')
    try:
        deck = powerpoint.Presentations.Open(pptx_path, WithWindow=False)
        deck.SaveAs(pdf_path, 32)
        deck.Close()
        print('PDF saved successfully.')
    finally:
        powerpoint.Quit()

    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        pix.save(os.path.join(out_dir, f'slide_{i+1:02d}.png'))
    print(f'Rendered {len(doc)} slides to {out_dir}')

if __name__ == '__main__':
    main()
