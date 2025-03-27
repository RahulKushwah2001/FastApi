from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, time
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

START_TIME = "08:00"
END_TIME = "18:00"

# Helper function to check if time is allowed
def is_time_allowed(entry_time: datetime) -> bool:
    open_time = entry_time.replace(hour=8, minute=0, second=0, microsecond=0)
    close_time = entry_time.replace(hour=18, minute=0, second=0, microsecond=0)
    return open_time <= entry_time <= close_time


def is_time(entry_time: datetime, open_time: time, close_time: time) -> bool:
    """Checks if the entry time is within the allowed open and close time."""
    check_in_time = entry_time.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
    check_out_time = entry_time.replace(hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0)
    return check_in_time <= entry_time <= check_out_time

def is_before_eight_am(entry_time: time) -> bool:
    reference_time = time(8, 0)
    return entry_time < reference_time

def is_after_six_pm(exit_time: time) -> bool:
    reference_time = time(18, 0)
    return exit_time > reference_time

class CheckInRequest(BaseModel):
    current_time: str  # Format: "HH:MM"
    action: str  # "checkin" or "checkout"
    quickID: str
    organization_name: str


class CheckTimeRequest(BaseModel):
    entry_time: str  # Format: "HH:MM"
    exit_time: str  # Format: "HH:MM"


@app.post("/check-in/")
async def check_in(request: CheckInRequest):
    try:
        current_time = datetime.strptime(request.current_time, "%H:%M")
        if not is_time_allowed(current_time):
            raise HTTPException(status_code=403, detail="Please check in between 08:00 AM and 06:00 PM.")

        if request.action.lower() == "checkin":
            logger.info(
                f"Visitor {request.quickID} checking in at {request.organization_name} at {current_time.strftime('%H:%M')}."
            )
            return {
                "message": f"Visitor {request.quickID} successfully checked in at {request.organization_name}.",
                "current_time": current_time.strftime("%H:%M")
            }
        elif request.action.lower() == "checkout":
            exit_time = current_time.replace(hour=18, minute=0)  # fixed to 6:00 PM
            logger.info(
                f"Visitor {request.quickID} checking out from {request.organization_name} at {exit_time.strftime('%H:%M')}."
            )
            return {
                "message": f"Visitor {request.quickID} successfully checked out from {request.organization_name} at {exit_time.strftime('%H:%M')}.",
                "current_time": current_time.strftime("%H:%M")
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid action. Use 'checkin' or 'checkout'.")

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Please use 'HH:MM' format for current_time.")


@app.post("/check-time/")
async def check_time(request: CheckTimeRequest):
    try:
        entry_time = datetime.strptime(request.entry_time, "%H:%M")
        exit_time = datetime.strptime(request.exit_time, "%H:%M")

        if not is_time_allowed(entry_time):
            raise HTTPException(status_code=403, detail="Entry time must be between 08:00 AM and 06:00 PM.")

        if exit_time < entry_time.replace(hour=18, minute=0, second=0, microsecond=0):
            raise HTTPException(status_code=403, detail="Exit time must be after 06:00 PM.")

        logger.info(
            f"Visitor will check-in at {entry_time.strftime('%H:%M')} and check-out at {exit_time.strftime('%H:%M')}."
        )
        return {
            "message": f"Check-in time: {entry_time.strftime('%H:%M')}, Check-out time: {exit_time.strftime('%H:%M')}. Proceeding with check-in.",
        }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format. Please use 'HH:MM' format for entry_time and exit_time."
        )

@app.get("/check-open-time")
def check_open_time():
    """Checks if the current time is after or equal to the open time."""
    open_time = time(8, 0)
    current_time = datetime.now()
    check_in_time = current_time.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
    return {"Open Time Check": current_time >= check_in_time,
            "Current Time": current_time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/check-close-time")
def check_close_time():
    """Checks if the current time is before or equal to the close time."""
    close_time = time(18, 0)
    current_time = datetime.now()
    check_out_time = current_time.replace(hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0)
    return {"Close Time Check": current_time <= check_out_time,
            "Current Time": current_time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/is-time-allowed")
def check_time_allowed():
    """Checks if the current time is within open and close time."""
    open_time = time(8, 0)
    close_time = time(18, 0)
    current_time = datetime.now()
    return {"Time Allowed": is_time(current_time, open_time, close_time),
            "Current Time": current_time.strftime("%Y-%m-%d %H:%M:%S")
    }

