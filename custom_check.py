import csv
import paramiko
import argparse
import logging
import select
from time import time

# Configure Logging to Info Level
logname='logs/custom_check_result.log'

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(filename=logname,
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

def main():
    # Set up argument parsing
    timestamp = int(time())
    parser = argparse.ArgumentParser(description='Execute remote commands from a CSV file')
    parser.add_argument('--server_ip',required=True, help='IP address of the server')
    parser.add_argument('--username',required=True, help='Username for the server')
    parser.add_argument('--private_key_path',required=True, help='Path to the private key file')
    parser.add_argument('--custom_commands',required=True, help='Path to the CSV file with commands')
    parser.add_argument('--output',required=True, help='Path to the output CSV file for failed commands')

    args = parser.parse_args()

    # Function to execute a command remotely
    # def execute_remote_command(ssh_client, command):
    #     # print('command', command)
    #     command = command.replace('\\n', '\n')
    #     try:
    #      stdin, stdout, stderr = ssh_client.exec_command(command, timeout=10)
    #     except Exception as e:
    #         return 1, '', str(e)

    #     return stdout.channel.recv_exit_status(), stdout.read(), stderr.read()

    def execute_remote_command(ssh_client, command, command_timeout=10):
        command = command.replace('\\n', '\n')
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = ''
        error = ''

        # Wait for the command to complete or timeout
        end_time = time() + command_timeout
        while not stdout.channel.closed or not stderr.channel.closed:
            if time() > end_time:
                return 1, '', 'Command timed out, make sure no interactive commands like "more", "less" etc'

            # Check if data is available on stdout or stderr
            ready, _, _ = select.select([stdout.channel, stderr.channel], [], [], command_timeout)
            if stdout.channel in ready:
                output += stdout.read().decode('utf-8')
            if stderr.channel in ready:
                error += stderr.read().decode('utf-8')

        exit_status = stdout.channel.recv_exit_status()
        return exit_status, output, error

    # Establish SSH connection
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=args.server_ip, username=args.username, key_filename=args.private_key_path)

    # Read CSV and execute commands
    failed_commands = []

    with open(args.custom_commands, 'r') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            print(f'checking: {row["id"]}')
            script = row['result']
            print('script', script)
            exit_code, stdout, stderr = execute_remote_command(ssh_client, script)
            print(f'exit_code: {exit_code}, stdout: {stdout}, stderr: {stderr}')
            # if returns stderr, it might fail.
            if stderr:
                if stdout:
                   logger.info(f'\n\ncustom check: {row["id"]} \n\nscript: {script} \n\nexit code: {exit_code} \n\nstdout: {stdout} \n\nstderr: {stderr} \n\n\n') 
                else:
                    logger.error(f"\n\nfailed custom check: {row['id']} \n\nfailed script: {script} \n\nstderr: {stderr} \n\nexit_code: {exit_code}\n\n\n")
                    failed_commands.append({'script': script, 'exit_code': exit_code, 'output': stderr})
            
            # if run surely succesfully 
            else:
                 logger.info(f'\n\ncustom check: {row["id"]} \n\nscript: {script} \n\nexit code: {exit_code} \n\nstdout: {stdout} \n\n\n')

    # Disconnect from server
    ssh_client.close()

    # Save failed commands to a new CSV
    with open(args.output, 'w', newline='') as csvfile:
        fieldnames = ['script', 'exit_code', 'output']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for command in failed_commands:
            writer.writerow(command)


if __name__=='__main__':
    main()
       
