from mcp.server.fastmcp import FastMCP
import subprocess
import re
import fcntl
import os
import time

mcp = FastMCP('gdb-mcp-server')
gdb = None
gdb_connected = False
debug_enabled = False

prompt = "(gdb)"

# ============================================================================
# utilities for GDB interaction
# ============================================================================

# Remove ANSI escape codes from GDB output for cleaner parsing
def remove_ansi_escape_codes(text: str) -> str:
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

# Clear the initial GDB stdout buffer until the prompt is reached
def clear_initial_buffer(timeout: int = 3) -> list:
    global gdb
    debug_log = []
    debug_log.append("[DEBUG] Clearing initial GDB output buffer...")
    
    start_time = time.time()
    collected = []
    empty_count = 0

    while True:
        try:
            line = gdb.stdout.readline()
            if line:
                empty_count = 0
                clean_line = remove_ansi_escape_codes(line)
                collected.append(clean_line)
                debug_log.append(f"[DEBUG] Initial Buffer: {repr(clean_line.strip())}")
            else:
                empty_count += 1
                if empty_count > 100:
                    debug_log.append("[DEBUG] Initial buffer empty-read threshold exceeded, stopping collect")
                    break
                time.sleep(0.01)
        except:
            time.sleep(0.01)

        if time.time() - start_time > timeout:
            debug_log.append(f"[DEBUG] Finished clearing initial buffer by timeout; collected {len(collected)} lines")
            break

    return debug_log, collected

# Execute a GDB command and capture its output until the prompt
def execute_cmd(cmd:str):
    global gdb, gdb_connected, debug_enabled

    debug_log = []
    debug_log.append(f"[DEBUG] execute_cmd called: {cmd}")

    if not gdb_connected:
        debug_log.append("[DEBUG] GDB is not connected.")
        error_msg = "GDB not connected - please run gdb_connect() first"
        return ("\n".join(debug_log) + "\n" + error_msg) if debug_enabled else error_msg

    if gdb is None:
        debug_log.append("[DEBUG] GDB subprocess is None.")
        error_msg = "GDB not connected - please run gdb_connect() first"
        return ("\n".join(debug_log) + "\n" + error_msg) if debug_enabled else error_msg

    debug_log.append("[DEBUG] Execute stdin.write()")
    gdb.stdin.write(cmd + "\n")
    gdb.stdin.flush()
    debug_log.append("[DEBUG] Finished stdin.flush()")

    output = []
    start_time = time.time()
    timeout = 10
    empty_count = 0

    while time.time() - start_time < timeout:
        try:
            line = gdb.stdout.readline()
            
            if line:
                empty_count = 0
                clean_line = remove_ansi_escape_codes(line)
                debug_log.append(f"[DEBUG] Received: {repr(clean_line)}")
                output.append(clean_line)
                
                if prompt in clean_line:
                    debug_log.append(f"[DEBUG] {prompt} prompt detected → stopping loop")
                    break
            else:
                empty_count += 1
                if empty_count > 100:
                    debug_log.append("[DEBUG] Empty read threshold exceeded, breaking loop to avoid infinite wait")
                    break
                time.sleep(0.01)
        except:
            time.sleep(0.01)

    debug_log.append("[DEBUG] execute_cmd loop exited")

    gdb_output = "".join(output)
    
    if debug_enabled:
        return "\n".join(debug_log) + "\n\n=== GDB OUTPUT ===\n" + gdb_output
    else:
        return gdb_output


# ============================================================================
# Server settings tools
# ============================================================================

# Enable debug mode
@mcp.tool()
def debug_mode():
    """Enable debug mode: include internal debug logs with tool outputs.

    When enabled, tools return both internal debug traces and GDB output,
    useful for diagnosing interactions during development or testing.
    """
    global debug_enabled
    debug_enabled = True
    return "✓ Debug mode enabled - debug logs will be included in all tool outputs"

# Disable debug mode
@mcp.tool()
def disable_debug_mode():
    """Disable debug mode: return only raw GDB outputs from tools.

    Use this for normal operation to avoid verbose internal logs.
    """
    global debug_enabled
    debug_enabled = False
    return "✓ Debug mode disabled - only GDB outputs will be shown"

# Plugin selection and prompt configuration
@mcp.tool()
def select_plugin(plugin: str):
    """select plugin (pwndbg, peda, gef, gdb) and set expected prompt"""

    global prompt, gdb_connected, gdb

    plugin = plugin.lower()
    valid = ['pwndbg', 'peda', 'gef', 'gdb']
    if plugin not in valid:
        return f"Invalid plugin. Choose from: {', '.join(valid)}"

    prompt_map = {
        'pwndbg': "pwndbg>",
        'peda':   "peda>",
        'gef':    "gef➤",
        'gdb':    "(gdb)"
    }

    prompt = prompt_map[plugin]

    if gdb_connected and gdb is not None:
        try:
            execute_cmd(f"set prompt {prompt}")
        except:
            pass

    return f"✓ Plugin set to {plugin} - expecting prompt: {prompt}"


# ============================================================================
# GDB tools
# ============================================================================

# Connection and session management
@mcp.tool()
def gdb_connect(target: str):
    global gdb, gdb_connected, debug_enabled

    """Start GDB as a subprocess and connect to the given target.

    `target` is passed to `gdb -q <target>`. If `target` begins with 'wsl '
    the prefix is removed to support WSL paths. This configures GDB stdout as
    non-blocking and drains initial output so the server begins in a clean
    state.
    """

    if target.startswith("wsl "):
        target = target[4:].strip()

    debug_log = []
    debug_log.append(f"[DEBUG] gdb_connect 호출됨: {target}")

    try:
        gdb = subprocess.Popen(
            ['gdb', '-q', target],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        bufsize=1  
    ) 
    except Exception as e:
        debug_log.append(f"[DEBUG] gdb subprocess 실행 실패: {e}")
        error_msg = "Failed to start GDB"
        return ("\n".join(debug_log) + "\n" + error_msg) if debug_enabled else error_msg

    debug_log.append("[DEBUG] subprocess.Popen 완료")

    fd = gdb.stdout.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    debug_log.append("[DEBUG] stdout non-blocking 모드 설정 완료")

    buffer_debug_log, initial_output = clear_initial_buffer(timeout=3)
    debug_log.extend(buffer_debug_log)

    gdb_connected = True

    initial_text = "".join(initial_output)

    if debug_enabled:
        return "\n".join(debug_log) + "\n\n=== INITIAL BUFFER ===\n" + initial_text

    return (
        f"✓ Connected to {target}\n"
        "=== INITIAL BUFFER ===\n"
        + initial_text + "\n"
        "Next: run select_plugin('pwndbg' | 'gef' | 'peda') to set the expected prompt.\n"
        "Vanilla gdb (no plugin): keep the default prompt '(gdb)'."
    )

@mcp.tool()
def start():
    """Start the program and stop at the first instruction (GDB 'starti')."""
    return execute_cmd('starti')

@mcp.tool()
def continue_exec():
    """Continue program execution until the next breakpoint or signal."""
    return execute_cmd('continue')

@mcp.tool()
def nexti():
    """Execute the next instruction, stepping over function calls (GDB 'ni')."""
    return execute_cmd('ni')

@mcp.tool()
def stepi():
    """Step into the next instruction or function call (GDB 'si')."""
    return execute_cmd('si')

@mcp.tool()
def finish():
    """Run until the current function returns (GDB 'finish')."""
    return execute_cmd('finish')

@mcp.tool()
def kill():
    """Terminate the debugged process (GDB 'kill')."""
    return execute_cmd('kill')

#Breakpoint commands
@mcp.tool()
def break_at(location: str):
    """Set a breakpoint at `location` (function, address, or file:line).

    Use to pause execution at a known point rather than stepping manually.
    """
    return execute_cmd(f'break {location}')

@mcp.tool()
def delete_breakpoints():
    """Delete all breakpoints in the current debug session."""
    return execute_cmd('delete')

@mcp.tool()
def info_breakpoints():
    """List breakpoints and their metadata (GDB 'info breakpoints')."""
    return execute_cmd('info breakpoints')

#Registers and stack inspection
@mcp.tool()
def regs():
    """Show CPU registers and their current values (GDB 'info registers')."""
    return execute_cmd('info registers')

@mcp.tool()
def stack():
    """Show stack contents or an enhanced stack view (plugin-specific 'stack')."""
    return execute_cmd('stack')

@mcp.tool()
def backtrace():
    """Get a stack backtrace of the current thread (GDB 'bt')."""
    return execute_cmd('bt')

@mcp.tool()
def frame(n: int):
    """Select stack frame `n` to inspect local variables (GDB 'frame N')."""
    return execute_cmd(f'frame {n}')

# Memory inspection
@mcp.tool()
def x(addr: str, count: int = 10):
    """Examine memory at `addr` (default: print `count` 8-byte hex words).

    Uses GDB 'x' formatting; adjust format specifiers as needed (xb, xh, xw).
    """
    return execute_cmd(f'x/{count}gx {addr}')

@mcp.tool()
def telescope(addr: str):
    """Invoke pwndbg's 'telescope' to dereference pointers and pretty-print memory.

    Requires the pwndbg plugin and helps inspect strings or linked structures.
    """
    return execute_cmd(f'telescope {addr}')

@mcp.tool()
def vmmap():
    """Show process memory mappings / address space layout (plugin-provided)."""
    return execute_cmd('vmmap')

# Symbols and functions
@mcp.tool()
def info_functions():
    """List functions and their addresses (GDB 'info functions')."""
    return execute_cmd('info functions')

@mcp.tool()
def disass(target: str):
    """Disassemble the specified symbol or address range (GDB 'disassemble')."""
    return execute_cmd(f'disassemble {target}')

@mcp.tool()
def info_symbols(name: str):
    """Show symbol information for `name` (GDB 'info symbol <name>')."""
    return execute_cmd(f'info symbol {name}')

# Binary security and metadata
@mcp.tool()
def checksec():
    """Run 'checksec' to display binary security mitigations (ASLR, NX, PIE).

    May use plugin helpers like pwndbg or gef for enhanced output.
    """
    return execute_cmd('checksec')

@mcp.tool()
def elf_info():
    """Show ELF metadata and section headers (plugin 'elfinfo')."""
    return execute_cmd('elfinfo')

@mcp.tool()
def got():
    """Display Global Offset Table (GOT) entries and resolved addresses."""
    return execute_cmd('got')

@mcp.tool()
def plt():
    """Display Procedure Linkage Table (PLT) entries for dynamic calls."""
    return execute_cmd('plt')

@mcp.tool()
def ropgadget():
    """Locate ROP gadgets using the integrated gadget finder (plugin 'rop')."""
    return execute_cmd('rop')

# Process and file information
@mcp.tool()
def info_proc():
    """Show process information such as pid and status (GDB 'info proc')."""
    return execute_cmd('info proc')

@mcp.tool()
def info_files():
    """Show file mappings and loaded object file information (GDB 'info files')."""
    return execute_cmd('info files')

@mcp.tool()
def target_remote(host: str, port: int):
    """connect to remote gdbserver (target remote host:port)"""
    return execute_cmd(f'target remote {host}:{port}')

# main
if __name__ == '__main__':
    mcp.run()