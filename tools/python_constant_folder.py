"""
Python Constant Folder & Optimizer
Statically parses Python source code into an AST, performs constant folding on literal
expressions (arithmetic, string concatenation, boolean logic), and outputs the optimized code.
"""
import argparse
import ast
import difflib
import sys

class ConstantFolder(ast.NodeTransformer):
    """AST transformer that folds constant expressions."""
    
    def __init__(self):
        super().__init__()
        self.folds_count = 0

    def visit_BinOp(self, node):
        # First recursively visit children
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        
        # Check if both sides are Constant
        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            val_left = node.left.value
            val_right = node.right.value
            
            try:
                # Safely evaluate binary operation
                result = None
                if isinstance(node.op, ast.Add):
                    result = val_left + val_right
                elif isinstance(node.op, ast.Sub):
                    result = val_left - val_right
                elif isinstance(node.op, ast.Mult):
                    # Guard against huge multiplication blockages
                    if (isinstance(val_left, (int, float)) and isinstance(val_right, (int, float)) and 
                            (abs(val_left) > 1e6 or abs(val_right) > 1e6)):
                        return node
                    if isinstance(val_left, str) and isinstance(val_right, int) and len(val_left) * val_right > 10000:
                        return node
                    if isinstance(val_right, str) and isinstance(val_left, int) and len(val_right) * val_left > 10000:
                        return node
                    result = val_left * val_right
                elif isinstance(node.op, ast.Div) and val_right != 0:
                    result = val_left / val_right
                elif isinstance(node.op, ast.FloorDiv) and val_right != 0:
                    result = val_left // val_right
                elif isinstance(node.op, ast.Mod) and val_right != 0:
                    result = val_left % val_right
                elif isinstance(node.op, ast.Pow):
                    # Prevent catastrophic exponentiation
                    if abs(val_right) > 100 or (isinstance(val_left, (int, float)) and abs(val_left) > 1000):
                        return node
                    result = val_left ** val_right
                
                if result is not None:
                    self.folds_count += 1
                    return ast.Constant(value=result)
            except Exception:
                # If evaluation fails, keep original node
                pass
                
        return node

    def visit_UnaryOp(self, node):
        node.operand = self.visit(node.operand)
        
        if isinstance(node.operand, ast.Constant):
            val = node.operand.value
            try:
                result = None
                if isinstance(node.op, ast.USub):
                    result = -val
                elif isinstance(node.op, ast.UAdd):
                    result = +val
                elif isinstance(node.op, ast.Not):
                    result = not val
                elif isinstance(node.op, ast.Invert):
                    result = ~val
                    
                if result is not None:
                    self.folds_count += 1
                    return ast.Constant(value=result)
            except Exception:
                pass
                
        return node

    def visit_BoolOp(self, node):
        # Optimize boolean short-circuit values
        node.values = [self.visit(val) for val in node.values]
        
        new_values = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                # For AND, if we hit False, the whole thing is False
                if isinstance(node.op, ast.And) and not val.value:
                    self.folds_count += 1
                    return ast.Constant(value=False)
                # For OR, if we hit True, the whole thing is True
                if isinstance(node.op, ast.Or) and val.value:
                    self.folds_count += 1
                    return ast.Constant(value=True)
                # Otherwise, skip redundant True (in AND) or False (in OR)
                if isinstance(node.op, ast.And) and val.value:
                    self.folds_count += 1
                    continue
                if isinstance(node.op, ast.Or) and not val.value:
                    self.folds_count += 1
                    continue
            new_values.append(val)
            
        if not new_values:
            # All were evaluated and removed (e.g. True and True and True)
            val = isinstance(node.op, ast.And)
            return ast.Constant(value=val)
            
        if len(new_values) == 1:
            return new_values[0]
            
        node.values = new_values
        return node


def main():
    parser = argparse.ArgumentParser(
        description="Statically fold constants and optimize Python source files."
    )
    parser.add_argument(
        "file",
        help="Path to the Python file to optimize."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to write the optimized file. If not specified, prints to stdout."
    )
    parser.add_argument(
        "-d", "--diff",
        action="store_true",
        help="Show unified diff of changes instead of writing/printing source."
    )
    parser.add_argument(
        "-i", "--inplace",
        action="store_true",
        help="Modify the source file in-place."
    )
    
    args = parser.parse_args()
    
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        sys.exit(1)
        
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"[ERROR] Syntax error in file: {e}")
        sys.exit(1)
        
    folder = ConstantFolder()
    optimized_tree = folder.visit(tree)
    ast.fix_missing_locations(optimized_tree)
    
    try:
        # ast.unparse is available in Python 3.9+
        optimized_source = ast.unparse(optimized_tree)
    except AttributeError:
        print("[ERROR] Constant folder requires Python 3.9+ (due to ast.unparse).")
        sys.exit(1)
        
    print(f"Optimization complete. Total constant folds performed: {folder.folds_count}", file=sys.stderr)
    
    if args.diff:
        diff = difflib.unified_diff(
            source.splitlines(keepends=True),
            optimized_source.splitlines(keepends=True),
            fromfile=args.file,
            tofile=args.file + " (optimized)"
        )
        sys.stdout.writelines(diff)
    elif args.inplace:
        if folder.folds_count > 0:
            try:
                with open(args.file, "w", encoding="utf-8") as f:
                    f.write(optimized_source)
                print(f"[OK] In-place optimization complete for '{args.file}'.", file=sys.stderr)
            except Exception as e:
                print(f"[ERROR] Failed to write in-place: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("[INFO] No optimizations were made. File left untouched.", file=sys.stderr)
    elif args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(optimized_source)
            print(f"[OK] Optimized source written to '{args.output}'.", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to write output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(optimized_source)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
