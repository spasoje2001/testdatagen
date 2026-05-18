import logging
import click
import sys
import os
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from testdatagen.log_config import setup_logging
from grammar_loader import load_model, validate_schema
from textx.exceptions import TextXSyntaxError
from validation import ValidationError
from testdatagen.generators.sql_generator import generate_sql
from testdatagen.generators.json_generator import generate_json
from testdatagen.generators.report_generator import generate_report

setup_logging()
logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ['sql', 'json', 'report']

@click.group()
@click.version_option(version="0.1.0")
def main():
    """TestDataGen - Intelligent test data generation based on DSL."""
    logger.info("TestDataGen CLI invoked.")

@main.command()
@click.argument('schema_file', type=click.STRING)
@click.option('--output', '-o', default='.', type=click.Path(), help='Output directory')
@click.option('--format', '-f', default='sql', help='Comma-separated formats (sql, json, report)')
@click.option('--seed', '-s', type=int, help='Override random seed for reproducibility')
@click.option('--overwrite', is_flag=True, help='Overwrite existing files in output directory')
def generate(schema_file, output, format, seed, overwrite):
    """Generate test data from a schema file."""
    
    formats = [f.strip().lower() for f in format.split(',')]
    invalid_formats = [f for f in formats if f not in SUPPORTED_FORMATS]
    
    if invalid_formats:
        raise click.BadParameter(f"Unsupported formats: {', '.join(invalid_formats)}. "
                                 f"Supported: {', '.join(SUPPORTED_FORMATS)}")
    
    temp_file_path = None
    try:
        if schema_file == '-':
            schema_content = sys.stdin.read()
            if not schema_content.strip():
                raise click.UsageError("Standard input is empty.")
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.tdg', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(schema_content)
                temp_file_path = temp_file.name
            target_file = temp_file_path
        else:
            if not os.path.exists(schema_file):
                raise click.BadParameter(f"Path '{schema_file}' does not exist.")
            target_file = schema_file

        validate_schema(target_file)

        if not os.path.exists(output):
            os.makedirs(output)
            logger.info(f"Created directory: {output}")

        model = load_model(target_file)
        
        if seed is not None:
            model.seed = seed

        with click.progressbar(formats, label='Generating files') as bar:
            for fmt in bar:
                if fmt == 'sql':
                    generate_sql(model, output, overwrite)
                elif fmt == 'json':
                    generate_json(model, output, overwrite)
                elif fmt == 'report':
                    generate_report(model, output, overwrite)

        click.secho(f"Success! Data generated in '{output}'", fg='green', bold=True)

    except (ValidationError, TextXSyntaxError) as e:
        click.secho(f"Cannot generate data. Schema validation failed:\n[Line {e.line}, Col {e.col}]: {e.message}", fg='red', err=True)
        sys.exit(1)

    except Exception as e:
        click.secho(f"\nError during generation: {str(e)}", fg='red', err=True)
        logger.error(f"Generation error: {e}", exc_info=True)
        sys.exit(2)

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@main.command()
@click.argument('schema_file', type=click.STRING)
def validate(schema_file):
    """Parse and validate schema without generating data."""
    click.echo(f"Validating {click.format_filename(schema_file)}...")
    
    temp_file_path = None
    try:
        if schema_file == '-':
            click.echo("Validating schema from [stdin]...")
            schema_content = sys.stdin.read()
            if not schema_content.strip():
                raise click.UsageError("Standard input is empty.")
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.tdg', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(schema_content)
                temp_file_path = temp_file.name
            target_file = temp_file_path
        else:
            click.echo(f"Validating {click.format_filename(schema_file)}...")
            if not os.path.exists(schema_file):
                raise click.BadParameter(f"Path '{schema_file}' does not exist.")
            target_file = schema_file

        detected_warnings = validate_schema(target_file)
        
        if detected_warnings:
            click.secho("\n Warnings detected during validation:", fg='yellow', bold=True)
            for warn in detected_warnings:
                click.secho(f"  - {warn}", fg='yellow')
            click.echo("")
            
        click.secho("Schema is syntactically and semantically valid.", fg='green', bold=True)
        sys.exit(0)

    except TextXSyntaxError as e:
        click.secho(f"Syntax Error [Line {e.line}, Col {e.col}]: {e.message}", fg='red', err=True)
        sys.exit(1)

    except ValidationError as e:
        click.secho(f"Semantic Error [Line {e.line}, Col {e.col}]: {e.message}", fg='red', err=True)
        sys.exit(1)

    except Exception as e:
        click.secho(f"System Error: {str(e)}", fg='red', err=True)
        sys.exit(1)

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == '__main__':
    main()
