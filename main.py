
import sys
from dotenv import load_dotenv


from prompts import fix_code_prompt, fix_test_prompt
from fixer import fix
from models import FixContext
from analysis import get_failing_tests, get_git_diff, read_file_content, run_tests
from utils import print_header, console


load_dotenv()

def main():

    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python test_fixer.py <project_path>[/yellow]")
        return

    print_header()
    
    path = sys.argv[1]
    run_tests(path)
    failures = get_failing_tests(path)

    if not failures:
        console.print("[green]All tests pass![/green]")
        return
    
    console.print(f"[yellow]Found {len(failures)} failing test(s)[/yellow]\n")

    for failure in failures:
        failing_test_file = failure['file']
        failing_test_function = failure['function']
        error_message = failure['error']

        console.print(f"[red]FAILING:[/red] {failing_test_file}::{failing_test_function}")
        console.print(f"[red]ERROR:[/red] {error_message}\n")


        test_file_path, test_code = read_file_content(failing_test_file, path)


        file_name = failing_test_file.split("/")[-1][5:]
        changed_files = get_git_diff(path)

        if file_name not in changed_files:
            if len(changed_files) == 1:
                file_name = changed_files[0]
                print("Found 1 changed file: ", file_name)

            else:
                print("Could not find source file, found these changed files:")
                for i, file in enumerate(changed_files, start=1):
                    print(f"{i:>3}  {file}")
                input_file = input("Select file by entering the number: ")
                file_name = changed_files[int(input_file)-1]

        file_path, function_code = read_file_content(file_name, path)

        choice = input("Fix [1] code or [2] test? (s to skip) ")
        if choice == "1":
            console.print("[blue]Proceeding to fix the code logic..[/blue]")
            context = FixContext(prompt=fix_code_prompt,
                            function_name=file_name,
                            file_path=file_path,
                            function_code=function_code,
                            test_code=test_code,
                            error_message=error_message,
                            repo_path=path,
                            test_file=failing_test_file,
                            test_function=failing_test_function)
            result = fix(context)
            if result:
                console.print("[green]✓ All tests passed successfully[/green]")
                break

        elif choice == "2":
            console.print("[blue]Proceeding to fix the failing test..[/blue]")
            context = FixContext(prompt=fix_test_prompt,
                            function_name=failing_test_function,
                            file_path=test_file_path,
                            function_code=function_code,
                            test_code=test_code,
                            error_message=error_message,
                            repo_path=path,
                            test_file=failing_test_file,
                            test_function=failing_test_function)
            result = fix(context)
            if result:
                console.print("[green]✓ All tests passed successfully[/green]")
                break
        elif choice.lower() == "s":
            continue
        else:
            console.print("[yellow]Invalid choice, skipping[/yellow]")
            continue            




if __name__ == "__main__":
    main()