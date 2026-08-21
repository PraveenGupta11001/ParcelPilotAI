import re

def clean_text(text: str) -> str:
    # Remove excessive blank lines and spaces
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def chunk_text(text: str, max_chunk_size: int = 800, min_chunk_size: int = 150) -> list[str]:
    cleaned = clean_text(text)
    paragraphs = cleaned.split('\n\n')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for p in paragraphs:
        p_len = len(p)
        if not p.strip():
            continue
        
        # If a single paragraph is extremely large, split by bullet points or sentences
        if p_len > max_chunk_size:
            # First flush current chunk if nonempty
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Split the large paragraph by bullet points or sentences
            subsections = re.split(r'(?=\n●|\n-|\. )', p)
            sub_chunk = []
            sub_size = 0
            for sub in subsections:
                sub = sub.strip()
                if not sub:
                    continue
                if sub_size + len(sub) > max_chunk_size:
                    if sub_chunk:
                        chunks.append(" / ".join(sub_chunk))
                    sub_chunk = [sub]
                    sub_size = len(sub)
                else:
                    sub_chunk.append(sub)
                    sub_size += len(sub)
            if sub_chunk:
                chunks.append(" / ".join(sub_chunk))
        else:
            if current_size + p_len > max_chunk_size:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [p]
                current_size = p_len
            else:
                current_chunk.append(p)
                current_size += p_len
                
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    # Filter out empty or mini chunks if appropriate, otherwise return all
    return [c.strip() for c in chunks if len(c.strip()) >= min_chunk_size or len(chunks) == 1]
