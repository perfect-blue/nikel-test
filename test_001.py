import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TransactionDataProcessor:
    def __init__(self):
        self.source_system = "API Gateway"
        self.current_year = datetime.now().year

    def process_data(self, input_data):
        """
        Process transaction data according to the required rules for consistency,
        security, and traceability.
        
        Args:
            input_data (dict): Raw transaction data
            
        Returns:
            dict: Processed transaction data
        """
        try:
            required_fields = ["message_type", "processing_code", "amount_tran", 
                              "primary_account_number", "transmission_date_time"]
            
            for field in required_fields:
                if field not in input_data:
                    logger.warning(f"Missing required field: {field}. Using default value.")
            
            output_data = {}

            output_data["transaction_amount"] = self._format_amount(
                input_data.get("amount_tran", "00000000")
            )

            output_data["primary_account_number_masked"] = self._mask_account_number(
                input_data.get("primary_account_number", "")
            )

            output_data["sender_account_number"] = self._encrypt_account_number(
                input_data.get("sender_account_number", "")
            )

            output_data["beneficiary_account_number_masked"] = self._mask_account_number(
                input_data.get("beneficiary_account_number", "")
            )

            transmission_date_time = input_data.get("transmission_date_time", "")
            formatted_time = self._format_datetime(transmission_date_time)
            output_data["transmission_date_time"] = formatted_time

            current_time = datetime.now()
            output_data["ingestion_timestamp"] = current_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            output_data["processing_duration"] = self._calculate_processing_duration(
                formatted_time, output_data["ingestion_timestamp"]
            )

            processing_code = input_data.get("processing_code", "")
            message_type = input_data.get("message_type", "")
            
            output_data["is_void"] = "true" if processing_code.startswith("02") else "false"
            output_data["is_reversal"] = "true" if message_type.startswith("14") else "false"

            output_data["status"] = "completed"
            output_data["source_system"] = self.source_system
            
            return output_data
            
        except Exception as e:
            logger.error(f"Error processing transaction data: {str(e)}")
            raise
    
    def _format_amount(self, amount_str):
        """Format amount string with two decimal places"""
        try:
            amount = float(amount_str) / 100
            return f"{amount:.2f}"
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount format: {amount_str}. Using default.")
            return "0.00"
    
    def _mask_account_number(self, account_number):
        """Mask account number, showing first 6 and last 4 digits"""
        if not account_number or len(account_number) < 10:
            logger.warning(f"Invalid account number format for masking: {account_number}")
            return account_number

        masked = account_number[:6] + "*" * (len(account_number) - 10) + account_number[-4:]
        return masked
    
    def _encrypt_account_number(self, account_number):
        """Mock encryption for account number"""
        if not account_number:
            logger.warning("Missing account number for encryption")
            return "encrypted_"
        
        return f"encrypted_{account_number}"
    
    def _format_datetime(self, datetime_str):
        """Format date time string to ISO 8601 format"""
        try:
            if not datetime_str or len(datetime_str) < 10:
                logger.warning(f"Invalid datetime format: {datetime_str}")
                return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")

            month = int(datetime_str[0:2])
            day = int(datetime_str[2:4])
            hour = int(datetime_str[4:6])
            minute = int(datetime_str[6:8])
            second = int(datetime_str[8:10])

            dt = datetime(self.current_year, month, day, hour, minute, second)

            return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except (ValueError, IndexError):
            logger.warning(f"Error parsing datetime: {datetime_str}. Using current time.")
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _calculate_processing_duration(self, start_time_str, end_time_str):
        """Calculate processing duration in seconds"""
        try:
            start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.000Z")
            end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%S.000Z")

            duration = (end_time - start_time).total_seconds()

            return f"{duration:.2f}"
        except (ValueError, TypeError):
            logger.warning("Error calculating processing duration. Using default.")
            return "5.00"


def main():
    # Sample input data
    sample_input = {
        "message_type": "2100",
        "processing_code": "0210",
        "amount_tran": "00005000",
        "primary_account_number": "1234567890123456",
        "sender_account_number": "9876543210987654",
        "beneficiary_account_number": "1122334455667788",
        "transmission_date_time": "1201153025",
        "transaction_date": "1201"
    }

    # Process the data
    processor = TransactionDataProcessor()
    try:
        result = processor.process_data(sample_input)

        print(json.dumps(result, indent=2))

        with open('processed_transaction.json', 'w') as f:
            json.dump(result, f, indent=2)

        logger.info("Processing completed successfully")
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")


if __name__ == "__main__":
    main()
