# 🔧 MCP Server for GDB

MCP server for GDB in WSL (supports pwndbg, gef, peda, and vanilla GDB)

![alt text](image.png)

# ⚙️ Settings

Register the following in your AI's configuration JSON:

```json
"gdb-mcp-server": {
      "command": "wsl",
      "args": [
        "-e",
        "python3",
        "path/to/server.py"
      ]
    }
```

After configuring as shown above, start your AI.

# 📝 Prompt Engineering

I primarily worked with Gemini as a reference. To prevent issues where Gemini uses shell commands instead of gdb even when gdb can handle the task, I prepared the following instructions for Gemini in advance:

```readme
Debugging Policy
All gdb-related actions must use pwndbg-mcp-server.
Never use the shell tool to run gdb.
Never prepend "wsl" to target paths.
The MCP server is already running inside WSL.
Target paths should be passed as absolute Linux paths (e.g., /home/jin/test2).
Tool Usage Rules
For debugging: call gdb_connect, run, checksec from pwndbg-mcp-server.
Do not ask for host/port.
Assume gdb-mcp-server is available.
```

# 🛠️ Tool List

## Server Settings
- **debug_mode** - Enable debug mode to include internal debug logs with tool outputs
- **disable_debug_mode** - Disable debug mode and return only raw GDB outputs

## Session Management
- **gdb_connect** - Start GDB as a subprocess and connect to the given target
- **select_plugin** - Select plugin (pwndbg, peda, or gef) to configure the correct prompt
- **target_remote** - Connect to remote gdbserver (target remote host:port)

## Execution Control
- **start** - Start the program and stop at the first instruction (GDB 'starti')
- **continue_exec** - Continue program execution until the next breakpoint or signal
- **nexti** - Execute the next instruction, stepping over function calls (GDB 'ni')
- **stepi** - Step into the next instruction or function call (GDB 'si')
- **finish** - Run until the current function returns (GDB 'finish')
- **kill** - Terminate the debugged process (GDB 'kill')

## Breakpoint Management
- **break_at** - Set a breakpoint at location (function, address, or file:line)
- **delete_breakpoints** - Delete all breakpoints in the current debug session
- **info_breakpoints** - List breakpoints and their metadata (GDB 'info breakpoints')

## Register and Stack Inspection
- **regs** - Show CPU registers and their current values (GDB 'info registers')
- **stack** - Show stack contents or an enhanced stack view (plugin-specific)
- **backtrace** - Get a stack backtrace of the current thread (GDB 'bt')
- **frame** - Select stack frame to inspect local variables (GDB 'frame N')

## Memory Inspection
- **x** - Examine memory at address (default: print 10 8-byte hex words)
- **telescope** - Invoke pwndbg's 'telescope' to dereference pointers and pretty-print memory
- **vmmap** - Show process memory mappings / address space layout

## Symbol and Function Inspection
- **info_functions** - List functions and their addresses (GDB 'info functions')
- **info_symbols** - Show symbol information for a name (GDB 'info symbol <name>')
- **disass** - Disassemble the specified symbol or address range (GDB 'disassemble')

## Binary Security and Metadata
- **checksec** - Display binary security mitigations (ASLR, NX, PIE) using checksec
- **elf_info** - Show ELF metadata and section headers
- **got** - Display Global Offset Table (GOT) entries and resolved addresses
- **plt** - Display Procedure Linkage Table (PLT) entries for dynamic calls
- **ropgadget** - Locate ROP gadgets using the integrated gadget finder

## Process and File Information
- **info_proc** - Show process information such as pid and status (GDB 'info proc')
- **info_files** - Show file mappings and loaded object file information (GDB 'info files')
