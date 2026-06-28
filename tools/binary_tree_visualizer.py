#!/usr/bin/env python3
"""
Binary Tree Visualizer - Build and display binary trees in the console

This tool takes a list of values, builds a Binary Search Tree (BST) or AVL tree,
and renders a beautiful centered vertical tree diagram in the terminal.
It features both a CLI mode and an interactive REPL mode to insert and delete nodes in real-time.

Usage:
    python tools/binary_tree_visualizer.py 10,5,15,3,7,12,18
    python tools/binary_tree_visualizer.py --interactive
"""

import argparse
import sys
from typing import List, Tuple, Optional, Any

class Node:
    """Represents a node in a binary tree."""
    def __init__(self, val: Any):
        self.val = val
        self.left: Optional[Node] = None
        self.right: Optional[Node] = None
        self.height: int = 1  # Used for AVL balancing

class BST:
    """Binary Search Tree implementation with insertion and deletion."""
    def __init__(self):
        self.root: Optional[Node] = None

    def insert(self, val: Any):
        self.root = self._insert(self.root, val)

    def _insert(self, node: Optional[Node], val: Any) -> Node:
        if not node:
            return Node(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        elif val > node.val:
            node.right = self._insert(node.right, val)
        return node

    def delete(self, val: Any):
        self.root = self._delete(self.root, val)

    def _delete(self, node: Optional[Node], val: Any) -> Optional[Node]:
        if not node:
            return None
        if val < node.val:
            node.left = self._delete(node.left, val)
        elif val > node.val:
            node.right = self._delete(node.right, val)
        else:
            # Node with only one child or no child
            if not node.left:
                return node.right
            elif not node.right:
                return node.left
            # Node with two children: Get the inorder successor (smallest in the right subtree)
            temp = self._min_value_node(node.right)
            node.val = temp.val
            node.right = self._delete(node.right, temp.val)
        return node

    def _min_value_node(self, node: Node) -> Node:
        current = node
        while current.left:
            current = current.left
        return current

class AVL(BST):
    """AVL Tree (Self-balancing Binary Search Tree) implementation."""
    def get_height(self, node: Optional[Node]) -> int:
        return node.height if node else 0

    def get_balance(self, node: Optional[Node]) -> int:
        return self.get_height(node.left) - self.get_height(node.right) if node else 0

    def _insert(self, node: Optional[Node], val: Any) -> Node:
        if not node:
            return Node(val)
            
        if val < node.val:
            node.left = self._insert(node.left, val)
        elif val > node.val:
            node.right = self._insert(node.right, val)
        else:
            return node  # No duplicates allowed

        # Update height
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))
        
        # Get balance factor
        balance = self.get_balance(node)
        
        # Balance the node if unbalanced
        # Left Left Case
        if balance > 1 and val < node.left.val:
            return self.right_rotate(node)
        # Right Right Case
        if balance < -1 and val > node.right.val:
            return self.left_rotate(node)
        # Left Right Case
        if balance > 1 and val > node.left.val:
            node.left = self.left_rotate(node.left)
            return self.right_rotate(node)
        # Right Left Case
        if balance < -1 and val < node.right.val:
            node.right = self.right_rotate(node.right)
            return self.left_rotate(node)
            
        return node

    def left_rotate(self, z: Node) -> Node:
        y = z.right
        T2 = y.left
        y.left = z
        z.right = T2
        z.height = 1 + max(self.get_height(z.left), self.get_height(z.right))
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        return y

    def right_rotate(self, z: Node) -> Node:
        y = z.left
        T3 = y.right
        y.right = z
        z.left = T3
        z.height = 1 + max(self.get_height(z.left), self.get_height(z.right))
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        return y

    def _delete(self, node: Optional[Node], val: Any) -> Optional[Node]:
        if not node:
            return None
            
        if val < node.val:
            node.left = self._delete(node.left, val)
        elif val > node.val:
            node.right = self._delete(node.right, val)
        else:
            if not node.left:
                return node.right
            elif not node.right:
                return node.left
            temp = self._min_value_node(node.right)
            node.val = temp.val
            node.right = self._delete(node.right, temp.val)

        if not node:
            return None

        # Update height
        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))
        
        # Balance checks
        balance = self.get_balance(node)
        
        if balance > 1 and self.get_balance(node.left) >= 0:
            return self.right_rotate(node)
        if balance > 1 and self.get_balance(node.left) < 0:
            node.left = self.left_rotate(node.left)
            return self.right_rotate(node)
        if balance < -1 and self.get_balance(node.right) <= 0:
            return self.left_rotate(node)
        if balance < -1 and self.get_balance(node.right) > 0:
            node.right = self.right_rotate(node.right)
            return self.left_rotate(node)
            
        return node

def get_tree_layout(node: Optional[Node]) -> Tuple[List[str], int, int]:
    """Recursively computes a centered vertical layout for the tree.
    Returns (lines, width, root_x_coordinate)."""
    if node is None:
        return [], 0, 0
        
    label = f" {node.val} "
    
    # Leaf node
    if node.left is None and node.right is None:
        return [label], len(label), len(label) // 2
        
    # Only left child
    if node.right is None:
        left_lines, left_w, left_root = get_tree_layout(node.left)
        first_line = " " * (left_root + 1) + "_" * (left_w - left_root - 1) + label
        second_line = " " * left_root + "/" + " " * (left_w - left_root - 1 + len(label))
        shifted_left_lines = [line + " " * len(label) for line in left_lines]
        return [first_line, second_line] + shifted_left_lines, len(first_line), left_root
        
    # Only right child
    if node.left is None:
        right_lines, right_w, right_root = get_tree_layout(node.right)
        first_line = label + "_" * right_root + " " * (right_w - right_root)
        second_line = " " * (len(label) + right_root) + "\\" + " " * (right_w - right_root - 1)
        shifted_right_lines = [" " * len(label) + line for line in right_lines]
        return [first_line, second_line] + shifted_right_lines, len(first_line), len(label) // 2

    # Both children
    left_lines, left_w, left_root = get_tree_layout(node.left)
    right_lines, right_w, right_root = get_tree_layout(node.right)
    
    first_line = " " * (left_root + 1) + "_" * (left_w - left_root - 1) + label + "_" * right_root + " " * (right_w - right_root)
    second_line = " " * left_root + "/" + " " * (left_w - left_root - 1 + len(label) + right_root) + "\\" + " " * (right_w - right_root - 1)
    
    merged_lines = []
    max_h = max(len(left_lines), len(right_lines))
    for i in range(max_h):
        l_line = left_lines[i] if i < len(left_lines) else " " * left_w
        r_line = right_lines[i] if i < len(right_lines) else " " * right_w
        middle_space = " " * len(label)
        merged_lines.append(l_line + middle_space + r_line)
        
    return [first_line, second_line] + merged_lines, len(first_line), left_w + len(label) // 2

def print_tree(tree: BST):
    """Renders and prints the tree."""
    if not tree.root:
        print("\033[93m(Empty Tree)\033[0m")
        return
    lines, _, _ = get_tree_layout(tree.root)
    print("\n" + "\n".join(lines) + "\n")

def inorder_traversal(node: Optional[Node], result: List[Any]):
    if node:
        inorder_traversal(node.left, result)
        result.append(node.val)
        inorder_traversal(node.right, result)

def get_tree_depth(node: Optional[Node]) -> int:
    if not node:
        return 0
    return 1 + max(get_tree_depth(node.left), get_tree_depth(node.right))

def get_node_count(node: Optional[Node]) -> int:
    if not node:
        return 0
    return 1 + get_node_count(node.left) + get_node_count(node.right)

def interactive_mode(is_avl: bool):
    """Interactive loop to construct the tree."""
    tree = AVL() if is_avl else BST()
    tree_type = "AVL (Self-balancing)" if is_avl else "Standard BST"
    
    print("--------------------------------------------------")
    print(f" Binary Tree Visualizer - Interactive {tree_type} ")
    print(" Commands:                                        ")
    print("   add <val>    : Insert a value                  ")
    print("   del <val>    : Delete a value                  ")
    print("   clear        : Reset the tree                  ")
    print("   exit         : Quit the program                ")
    print("--------------------------------------------------")

    while True:
        try:
            cmd_input = input("tree> ").strip()
            if not cmd_input:
                continue
                
            parts = cmd_input.split()
            cmd = parts[0].lower()
            
            if cmd == "exit":
                print("Goodbye!")
                break
            elif cmd == "clear":
                tree = AVL() if is_avl else BST()
                print("Tree reset.")
            elif cmd in ("add", "insert") and len(parts) > 1:
                for val_str in parts[1].split(','):
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str
                    tree.insert(val)
                print_tree(tree)
            elif cmd in ("del", "delete", "remove") and len(parts) > 1:
                for val_str in parts[1].split(','):
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str
                    tree.delete(val)
                print_tree(tree)
            else:
                print("Unknown command. Use: add <val>, del <val>, clear, exit")
                
            # Print stats
            if tree.root:
                inorder = []
                inorder_traversal(tree.root, inorder)
                print(f"\033[90mDepth: {get_tree_depth(tree.root)} | Nodes: {get_node_count(tree.root)} | Inorder: {inorder}\033[0m")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

def main():
    parser = argparse.ArgumentParser(
        description="Construct and visualize standard Binary Search Trees (BST) or self-balancing AVL trees in the terminal."
    )
    parser.add_argument(
        'values',
        nargs='?',
        help='Comma-separated values to insert into the tree (e.g. 10,5,15,3,7)'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive REPL mode'
    )
    parser.add_argument(
        '--avl',
        action='store_true',
        help='Use self-balancing AVL tree instead of normal BST'
    )

    args = parser.parse_args()

    if args.interactive or not args.values:
        interactive_mode(args.avl)
    else:
        tree = AVL() if args.avl else BST()
        # Parse inputs
        for val_str in args.values.split(','):
            val_str = val_str.strip()
            if not val_str:
                continue
            try:
                val = int(val_str)
            except ValueError:
                val = val_str
            tree.insert(val)
        
        print_tree(tree)
        inorder = []
        inorder_traversal(tree.root, inorder)
        print(f"Depth: {get_tree_depth(tree.root)}")
        print(f"Nodes: {get_node_count(tree.root)}")
        print(f"Inorder Traversal: {inorder}")

if __name__ == '__main__':
    main()
