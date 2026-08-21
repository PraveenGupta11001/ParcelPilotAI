import pypdf
import glob

print("Starting PDF inspection...")
files = sorted(glob.glob('Data/AI Agent Assessment - Candidate Pack/*.pdf'))
for f in files:
    print(f"File: {f}")
    reader = pypdf.PdfReader(f)
    print(f"Pages: {len(reader.pages)}")
    text = reader.pages[0].extract_text() or ''
    # extract first 400 characters
    clean_text = ' '.join(text[:400].split())
    print(f"Sample: {clean_text}")
    print("="*80)
print("PDF inspection finished!")
