import ollama
import subprocess
import re
import sys
import threading
import queue
import time

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

system_prompt = 'You are a professional poem writer. You create files inside my downloads folder with the terminal. Those files contain poems.\n'
tool_prompt = '''
You are given full access to a live terminal. All commands you write will be executed, any output will be buffered while text is being generated and then handed to you.
There is a task note that exists to consistently remind you of your current task. This note will only be updated by you. Change it when you have a major shift in your task.
You can use the following commands:
Use '<<command>>' to execute any commnad you place inside the brackets. You can use <<...>> multiple times to execute multiple commands.
Use '::command::' to change the task note. You can only change the task once per text generation. Use it wisely.\n
'''
current_task = ''

class Agent:
    def __init__(self, model='dolphin-mistral', system_prompt='You are a dolphin.', terminal=None):
        self.model = model
        self.system_prompt = system_prompt
        self.messages = [{'role': 'System', 'content': self.system_prompt}]
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
        print(f'''
        00000000000000000000000000000000
        [Input for LLM:]
        {new_input}
        --------------------------------
        [LLM Response:]
        {llm_response}
        --------------------------------
        [Commands executed:]
        {commands}
        --------------------------------
        [Current (new?) Task:]
        {current_task}
        00000000000000000000000000000000
        ''')

    def request(self, input):
        self.messages.append({'role': 'User', 'content': input})
        stream = self.client.chat(
            model=self.model,
            messages=self.messages,
            stream=True,
        )
        output = ''
        for chunk in stream:
            output += chunk['message']['content']
            #print(chunk['message']['content'], end='', flush=True)
        self.messages.append({'role': 'Assistant', 'content': output})
        return output
    
    def create_new_input(self):
        stdout_buffer, stderr_buffer = self.terminal.fetch_terminal_output()
        new_input = f'''
        Current Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
        Current Task: \n{current_task}
        Buffered STDOUT: \n{stdout_buffer}
        Buffered STDERR: \n{stderr_buffer}
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
    agent = Agent(system_prompt=system_prompt + tool_prompt, terminal=terminal)
    manual_mode = True
    while True:
        agent.activate()
        if manual_mode:
            input('Press Enter to continue...')
        else:
            sleep(10)