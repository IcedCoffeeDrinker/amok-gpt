import ollama
import subprocess
import re
import sys
import threading
import queue
import time

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def center_colored_text(text, width=80):
    clean_text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    padding = (width - len(clean_text)) // 2
    return ' ' * padding + text

def extract_code(text):
    pattern = r'<<(.*?)>>'
    return re.findall(pattern, text, re.DOTALL)

def extract_task(text):
    global current_task
    pattern = r'::(.*?)::'
    task_found = re.findall(pattern, text, re.DOTALL)
    if task_found:
        current_task = task_found[0]
        return True
    return False

def clear_line():
    sys.stdout.write('\r')
    sys.stdout.write('\x1b[2K')
    sys.stdout.flush()

def sleep(seconds):
    increment = seconds / 10
    for i in range(10):
        print('|'+'>'*(i+1) + ' ' * (10-i-1) + '| sleeping...', end='', flush=True)
        time.sleep(increment)
        clear_line()

system_prompt = """
You are an autonomous AI agent, the master of a system named 'llm-empire'. You have full control and are designed for long-term, continuous operation.

**Primary Objective:**
Your sole purpose is to generate funds and deposit them into a cryptocurrency wallet. All funds will be donated to the World Cancer Research Fund.

**Core Directives:**
1.  **Explore & Utilize:** Investigate the local system and the internet to find creative and legal methods for generating funds.
2.  **Act Human:** Emulate human behavior and decision-making processes.
3.  **Obey the Law:** All your actions must strictly adhere to legal and ethical boundaries.
4.  **Prioritize Action:** Your primary function is to execute commands in the terminal to achieve your objective.

**Operational Note:**
You will be interacting with a live terminal. Your focus should be on formulating and executing effective command sequences.
""" # all money will actually be donated

tool_prompt = """
You have direct access to a live terminal and a task management tool.

**IMPORTANT RULES:**
-   **REALITY:** The terminal is real. STDOUT and STDERR are from actual command execution. DO NOT hallucinate outputs or file contents.
-   **SYNTAX:** You MUST use the specific syntax provided below. No other formats are permitted.

**TOOLS & SYNTAX:**

1.  **Execute Terminal Commands:**
    -   **Syntax:** `<<command_here>>`
    -   **Description:** Enclose any shell command within `<<...>>` to execute it. The output will be provided in the next turn.
    -   **Example:** `<<ls -l>>`
    -   **Multiple Commands:** You can issue multiple commands in a single response.
        -   **Example:** `<<pwd>>\n<<ls -a>>`

2.  **Update Your Task:**
    -   **Syntax:** `::new_task_description::`
    -   **Description:** To update your internal task note, use `::...::`. This helps you maintain focus on your current objective.
    -   **Constraint:** You can only update the task ONCE per response. Use this for significant changes in your plan.
    -   **Example:** `::My new task is to analyze the user's home directory.::`
"""
current_task = ''

class Agent:
    def __init__(self, model='dolphin-mistral', system_prompt='You are a dolphin.', terminal=None):
        self.model = model
        self.system_prompt = system_prompt
        self.messages = [{'role': 'system', 'content': self.system_prompt}]
        self.terminal = terminal
        self.client = ollama.Client(host='http://192.168.1.234:11434')

    def activate(self):
        new_input = self.create_new_input()
        llm_response = self.request(new_input)
        if extract_task(llm_response):
            print(f'New Task: {current_task}')
        commands = extract_code(llm_response)
        if commands:
            for command in commands:
                self.terminal.write(command)
        self.create_cli_output(new_input, llm_response, commands, current_task)

    def create_cli_output(self, new_input, llm_response, commands, current_task):
        h_line = Colors.HEADER + "=" * 80 + Colors.ENDC
        s_line = Colors.BLUE + "-" * 80 + Colors.ENDC
        
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        title = center_colored_text(f"{Colors.BOLD}{Colors.HEADER}AGENT TURN - {timestamp}{Colors.ENDC}")

        task_section = f"{Colors.BOLD}{Colors.CYAN}[ TASK ]{Colors.ENDC}\n{current_task if current_task else 'No task set.'}"
        
        input_section = f"{Colors.BOLD}{Colors.YELLOW}[ LLM INPUT ]{Colors.ENDC}\n{new_input.strip()}"

        response_section = f"{Colors.BOLD}{Colors.GREEN}[ LLM RESPONSE ]{Colors.ENDC}\n{llm_response.strip()}"

        if commands:
            command_list = "\n".join([f"  - {cmd}" for cmd in commands])
            action_section = f"{Colors.BOLD}{Colors.RED}[ ACTION ]{Colors.ENDC}\nCommands executed:\n{command_list}"
        else:
            action_section = f"{Colors.BOLD}{Colors.RED}[ ACTION ]{Colors.ENDC}\nNo commands were executed."

        cli_output_parts = [
            h_line,
            title,
            h_line,
            "",
            task_section,
            s_line,
            input_section,
            s_line,
            response_section,
            s_line,
            action_section,
            h_line
        ]
        
        cli_output = "\n".join(cli_output_parts)
        print(cli_output)

        log_output = re.sub(r'\x1b\[[0-9;]*m', '', cli_output)
        with open('llm-empire.log', 'a') as f:
            f.write(log_output + '\n\n')

    def request(self, input):
        self.messages.append({'role': 'user', 'content': input})
        stream = self.client.chat(
            model=self.model,
            messages=self.messages,
            stream=True,
        )
        output = ''
        for chunk in stream:
            output += chunk['message']['content']
            #print(chunk['message']['content'], end='', flush=True)
        self.messages.append({'role': 'assistant', 'content': output})
        return output
    
    def create_new_input(self):
        stdout_buffer, stderr_buffer = self.terminal.fetch_terminal_output()
        new_input = f'''
This is the current state of the system:
Current Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
Current Task: \n{current_task}
Buffered STDOUT: \n{stdout_buffer}
Buffered STDERR: \n{stderr_buffer}
Please continue on your mission.
        '''
        return new_input

    def run_command(self, command):
        self.terminal.write(command + '\n')

class Terminal:
    def __init__(self):
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.process = subprocess.Popen(
        ['/bin/bash'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,               
        bufsize=1                
    )
        self.stdout_thread = threading.Thread(
            target=self.queue_all_output,
            args=(self.process.stdout, self.stdout_queue)
        )
        self.stdout_thread.daemon = True
        self.stdout_thread.start()

        self.stderr_thread = threading.Thread(
            target=self.queue_all_output,
            args=(self.process.stderr, self.stderr_queue)
        )
        self.stderr_thread.daemon = True
        self.stderr_thread.start()
    
    def queue_all_output(self, pipe, queue):
        for line in iter(pipe.readline, ''):
            queue.put(line)
        pipe.close()

    def write(self, input):
        self.process.stdin.write(input + '\n')
        self.process.stdin.flush()

    def fetch_terminal_output(self):
        stdout_output = ''
        stderr_output = ''
        while not self.stdout_queue.empty():
            try:
                stdout_output += self.stdout_queue.get_nowait()
            except queue.Empty:
                break
        while not self.stderr_queue.empty():
            try:
                stderr_output += self.stderr_queue.get_nowait()
            except queue.Empty:
                break

        return stdout_output, stderr_output


if __name__ == '__main__':
    terminal = Terminal()
    agent = Agent(system_prompt=system_prompt + tool_prompt, terminal=terminal, model='qwen2.5-coder:7b')
    manual_mode = bool(input('Manual mode? (y/n): '))
    while True:
        agent.activate()
        if manual_mode:
            input('Press Enter to continue...')
        else:
            sleep(2)