import os
import glob
import subprocess

def main():
    image_dir = '/home/thomas/.gemini/antigravity/brain/35c2d10f-5438-4b4e-8549-7a894227b837'
    output_file = '/home/thomas/.gemini/antigravity/brain/35c2d10f-5438-4b4e-8549-7a894227b837/module1_extracted_text.md'
    
    # Get all module 1 images
    images = glob.glob(os.path.join(image_dir, 'module1_page*.png'))
    
    # Sort images based on page numbers
    def extract_page_num(filename):
        # Extract the part like "page1", "page2" and get the number
        basename = os.path.basename(filename)
        try:
            parts = basename.split('_')
            for part in parts:
                if part.startswith('page'):
                    return int(part[4:])
        except:
            pass
        return 999
        
    images.sort(key=extract_page_num)
    
    with open(output_file, 'w') as out_f:
        out_f.write('# Module 1 Extracted Text\n\n')
        
        for img in images:
            print(f"Processing {img}...")
            # Use tesseract for OCR
            try:
                # Provide output base name without extension, tesseract adds .txt
                base_out = '/home/thomas/development/internal/FuckWiley/tesseract_out'
                subprocess.run(['tesseract', img, base_out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                with open(base_out + '.txt', 'r') as in_f:
                    text = in_f.read()
                    
                page_name = os.path.basename(img)
                out_f.write(f'## Page: {page_name}\n\n')
                out_f.write(text)
                out_f.write('\n\n---\n\n')
            except Exception as e:
                print(f"Error processing {img}: {e}")
                
    print(f"Extraction complete. Output saved to {output_file}")

if __name__ == '__main__':
    main()
