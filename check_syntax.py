import ast
import sys

file_path = r"C:\Users\win10_original\Downloads\ha-ezville-wallpad\custom_components\ezville_wallpad\rs485_client.py"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count lines
    lines = content.split('\n')
    print(f"Total lines in file: {len(lines)}")
    
    # Try to parse
    ast.parse(content)
    print("File syntax is valid!")
    
except SyntaxError as e:
    print(f"Syntax error found!")
    print(f"Line: {e.lineno}")
    print(f"Text: {e.text}")
    print(f"Error: {e.msg}")
    
    # Show lines around the error
    if e.lineno:
        start = max(0, e.lineno - 5)
        end = min(len(lines), e.lineno + 5)
        print(f"\nLines {start+1} to {end}:")
        for i in range(start, end):
            marker = ">>>" if i + 1 == e.lineno else "   "
            print(f"{marker} {i+1}: {lines[i]}")
            
except Exception as e:
    print(f"Error reading file: {e}")
