import os
import sys
import rich_click as click
from .service_managers import select_service_manager

@click.group()
@click.pass_context
def service(ctx):
    """Manage the program as a service (executable only)"""
    ctx.ensure_object(dict)
    if os.getenv("PYAPP") is None:
        print("Service commands are only available in the executable version of the program")
        sys.exit(1)
    ctx.obj["service_manager"] = select_service_manager()(os.getenv("PYAPP"))

@service.command()
@click.pass_context
def start(ctx):
    """Start the service"""
    ctx.obj["service_manager"].start()
    
@service.command()
@click.pass_context
def stop(ctx):
    """Stop the service"""
    ctx.obj["service_manager"].stop()

@service.command()
@click.pass_context
def restart(ctx):
    """Restart the service"""
    ctx.obj["service_manager"].restart()
    
@service.command()
@click.pass_context
def status(ctx):
    """Get the status of the service"""
    ctx.obj["service_manager"].status()

@service.command()
@click.pass_context
def install(ctx):
    """Install the service"""
    ctx.obj["service_manager"].install()

@service.command()
@click.pass_context
def uninstall(ctx):
    """Uninstall the service"""
    ctx.obj["service_manager"].uninstall()

@service.command()
@click.pass_context
def enable(ctx):
    """Enable the service"""
    ctx.obj["service_manager"].enable()

@service.command()
@click.pass_context
def disable(ctx):
    """Disable the service"""
    ctx.obj["service_manager"].disable()

