from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Query,BackgroundTasks
from app.api.stage.services.shop import ShopService
from app.api.stage.services.users import UserService
from app.utils.logging import log_request_response
from ..helpers.string_helper import StringHelper
from ..models.address import GeoLocation
from ..models.business_model import CheckIfWithinPayload
from ..models.visit import CheckIn, UpdateVisitData, PaginatedResponse, VisitQueryParams, WeeklyVisitCount
from ..services import visit
from app.utils.redis import Redis
from datetime import datetime
from ..services.business import BusinessService
from ....config import DUMMY_QUICKIDS,CHECK_IN_RADIUS

router = APIRouter()


@router.post("/check-in")
def check_in(request: Request, check_in_data: CheckIn):
    quickID = request.state.user['quickID']
    
    redis_key = f"visit:{quickID}"
    ttl = Redis.get_ttl(redis_key)
    if ttl and ttl > 0: raise HTTPException(status_code=429, detail=f"Wait for {ttl} seconds.")
    Redis.set(redis_key, '1', 60)

    # Fetch shop's business details, including closing time
    business_details = ShopService.get_shop_business_details(
        check_in_data.shop_quickID, ['website', 'closing_time'])

    # Ensure that the business details contain a valid closing time
    closing_time_str = business_details.get('closing_time')
    if closing_time_str:
        # Convert the closing time to a datetime object
        closing_time = datetime.strptime(closing_time_str, "%H:%M").time()  # Assuming time format like "23:59"

        current_time = datetime.now().time()

        # Check if the current time is after the closing time
        if current_time > closing_time:
            raise HTTPException(status_code=400, detail="QR check-in is deactivated after closing time.")

    distance = visit.check_inside_shop(
        check_in_data.shop_quickID, check_in_data.location)
    if distance >= CHECK_IN_RADIUS and not quickID in DUMMY_QUICKIDS:
        raise HTTPException(status_code=400, detail=f"out of {CHECK_IN_RADIUS} meter radius")
    active_visit = visit.get_active_visits(quickID)
    business_details = ShopService.get_shop_business_details(
        check_in_data.shop_quickID, ['website'])
    if business_details['black_list'] and quickID in business_details['black_list']: raise HTTPException(status_code=400, detail=f"you are blacklisted in this shop")
    if active_visit:
        if active_visit['shop_quickID'] == check_in_data.shop_quickID:
            active_visit['store_website'] = business_details['business'].get('website')
            msg, is_shop_calibrated = BusinessService.is_shop_calibrated(
                check_in_data.shop_quickID)
            result = visit.check_out_visit(
                quickID, active_visit, 'QR', 'checked out using QR', check_in_data.location)
            result['user_name'] = StringHelper.mask_user_name(
                result['user_name'])
            result['store_website'] = business_details['business'].get('website')
            result['is_shop_calibrated'] = is_shop_calibrated
            result['user_aadhaar_picture'] = UserService.get_user_aadhar_picture(
                quickID)
            result['user_first_name'] = result['user_name'].split(' ')[0]
            return result
        visit.check_out_visit(quickID, active_visit, 'QR',
                              'checked in at another store', check_in_data.location)
    check_in = visit.check_in(quickID, check_in_data)
    check_in['store_website'] = business_details['business']['website']
    msg, is_shop_calibrated = BusinessService.is_shop_calibrated(
        check_in_data.shop_quickID)
    check_in['user_name'] = StringHelper.mask_user_name(check_in['user_name'])
    check_in['user_first_name'] = check_in['user_name'].split(' ')[0]
    check_in['is_shop_calibrated'] = is_shop_calibrated
    check_in['user_aadhaar_picture'] = UserService.get_user_aadhar_picture(
        quickID)
    return check_in


@router.get("/active-visit")
def active_visit(request: Request):
    quickID = request.state.user['quickID']
    current_visit = visit.get_active_visits(quickID)
    is_shop_calibrated = False
    if current_visit:
        business_details = ShopService.get_shop_business_details(
            current_visit['shop_quickID'], ['website'])
        current_visit['store_website'] = business_details['business'].get('website')
        shop_quickID = current_visit['shop_quickID']
        msg, is_shop_calibrated = BusinessService.is_shop_calibrated(
            shop_quickID)
        current_visit['user_name'] = StringHelper.mask_user_name(
            current_visit['user_name'])
        current_visit['user_first_name'] = current_visit['user_name'].split(' ')[
            0]
        current_visit['is_shop_calibrated'] = is_shop_calibrated
        current_visit['user_aadhaar_picture'] = UserService.get_user_aadhar_picture(
            quickID)
    return current_visit


@router.put("/")
def update_visit(request: Request, data_to_update: UpdateVisitData):
    quickID = request.state.user['quickID']
    active_visit = visit.get_active_visits(quickID)
    if not active_visit:
        raise HTTPException(status_code=404, detail="no current visit found")
    shop_quickID = active_visit['shop_quickID']
    msg, is_shop_calibrated = BusinessService.is_shop_calibrated(shop_quickID)
    update_visit_resp = visit.update_visit(
        quickID, active_visit, data_to_update)
    update_visit_resp['user_aadhaar_picture'] = UserService.get_user_aadhar_picture(
        quickID)
    update_visit_resp['is_shop_calibrated'] = is_shop_calibrated
    return update_visit_resp


@router.get("/", response_model=PaginatedResponse)
def get_visits(request: Request, query_params: VisitQueryParams = Depends()):
    query_params.quickID = request.state.user['quickID']
    if query_params.role not in ["user", "shop_owner"]:
        raise HTTPException(
            status_code=400, detail="Invalid role. Use 'user' or 'shop_owner'.")

    try:
        datetime.strptime(query_params.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use 'YYYY-MM-DD'.")

    # Fetch data using the VisitRepository
    try:
        visits, total_count, total_pages = visit.get_visits(
            filter_params=query_params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database query failed:- {e}")

    return PaginatedResponse(page=query_params.page, page_size=query_params.page_size, total_records=total_count, total_pages=total_pages, data=visits)


@router.get("/pov")
def visit_pov():
    return ['Visitor', 'Guest', 'Delivery', 'Courier', 'Maintanence', 'Vendor', 'Other']


@router.post("/geo-check-out")
async def geo_checkout(
    request: Request,
    location: GeoLocation,
    background_tasks: BackgroundTasks,
    ssids: Optional[List[CheckIfWithinPayload]] = None,
):
    try:
        print(F"--------------- the user ssids are {ssids}")
        quickID = request.state.user['quickID']
        current_visit = visit.is_out_of_range(quickID, location)
        if not current_visit:
            print('No current visit found')
            raise HTTPException(
                status_code=404, detail="No current visit found")
        shop_quickID = current_visit['shop_quickID']
        msg, is_shop_calibrated = BusinessService.is_shop_calibrated(
            shop_quickID)
        is_within_shop_ssids = False
        if ssids:
            if not is_shop_calibrated and len(ssids) > 2:
                for ssid in ssids:
                    BusinessService.seed_ssids(shop_quickID, ssid)
            else:
                _, is_within_shop_ssids = BusinessService.check_if_within(
                    shop_quickID, ssids)
        warning_count = visit.get_warning_count(quickID,current_visit)
        resp = { "warning_count" : warning_count, "checked_out": False, "time": None, "distance": current_visit['distance'], "wifi": is_within_shop_ssids, "location": current_visit['distance'] < CHECK_IN_RADIUS }
        if current_visit['distance'] < CHECK_IN_RADIUS or is_within_shop_ssids:
            print(resp)
            background_tasks.add_task(log_request_response, quickID, 'visit',current_visit['visit_id'], location.dict(), str(resp))
            return resp
        update_warning = visit.increase_warnings(quickID,current_visit,warning_count)
        time = None
        checked_out = False
        if update_warning['updated_warning_count'] >3:
            result = visit.check_out_visit( quickID, current_visit, 'Geo Tagged', f'out of {CHECK_IN_RADIUS} meter radius', location )
            time = result['time']
            checked_out=True
        resp = {"warning_count" : update_warning['updated_warning_count'], "checked_out": checked_out, "time": time, "distance": current_visit['distance'], "wifi": is_within_shop_ssids, "location": current_visit['distance'] < CHECK_IN_RADIUS }
        print(resp)
        background_tasks.add_task(log_request_response, quickID, 'visit',current_visit['visit_id'], location.dict(), str(resp))
        return resp
    except HTTPException as e:
        print(f'{e}')
        raise e
    except Exception as e:
        print(f'{e}')
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the request: {str(e)}"
        )


@router.get("/weekly")
def get_weekly_visits(request: Request, query_params: WeeklyVisitCount = Depends()):
    quickID = request.state.user['quickID']
    return visit.get_weekly_visits(quickID, query_params.start_date)


@router.get("/count")
def visit_count(request: Request, date=Query(..., description="Date for filtering visit count (YYYY-MM-DD)")):
    quickID = request.state.user['quickID']
    return visit.get_visit_count(quickID, date)


@router.get("/{visit_id}")
def get_visit(visit_id: str):
    return visit.get_visit_by_id(visit_id)
