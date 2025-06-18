#!/usr/bin/env python3
"""
Test script to verify use case configuration is working correctly.
This tests the backend configuration without any UI components.
"""

import os
import json
import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

def test_use_case_config():
    """Test the use case configuration system"""
    
    print("🧪 Testing Use Case Configuration System")
    print("=" * 50)
    
    # Test 1: Environment Variables
    print("\n1. Testing Environment Variables...")
    os.environ["USE_CASES"] = '["credit_risk_modeling", "fraud_detection"]'
    os.environ["USE_CASE_FILTER_ENABLED"] = "true"
    
    try:
        from utils.resources import get_use_case_config
        config = get_use_case_config()
        print(f"✅ Config from env vars: {config}")
        
        expected = {
            "use_cases": ["credit_risk_modeling", "fraud_detection"],
            "use_case_filter_enabled": True
        }
        
        if config == expected:
            print("✅ Environment variable configuration working correctly")
        else:
            print(f"❌ Environment variable configuration failed. Expected: {expected}, Got: {config}")
            
    except Exception as e:
        print(f"❌ Environment variable test failed: {str(e)}")
    
    # Test 2: app_infra.json
    print("\n2. Testing app_infra.json...")
    try:
        # Create a test app_infra.json
        test_config = {
            "database": "no_database",
            "llm": "azure_openai",
            "use_cases": ["loan_approval", "portfolio_management"],
            "use_case_filter_enabled": True
        }
        
        with open("frontend/app_infra.json", "w") as f:
            json.dump(test_config, f, indent=4)
        
        # Clear environment variables to test app_infra.json fallback
        if "USE_CASES" in os.environ:
            del os.environ["USE_CASES"]
        if "USE_CASE_FILTER_ENABLED" in os.environ:
            del os.environ["USE_CASE_FILTER_ENABLED"]
        
        config = get_use_case_config()
        print(f"✅ Config from app_infra.json: {config}")
        
        expected = {
            "use_cases": ["loan_approval", "portfolio_management"],
            "use_case_filter_enabled": True
        }
        
        if config == expected:
            print("✅ app_infra.json configuration working correctly")
        else:
            print(f"❌ app_infra.json configuration failed. Expected: {expected}, Got: {config}")
            
    except Exception as e:
        print(f"❌ app_infra.json test failed: {str(e)}")
    
    # Test 3: Default Configuration
    print("\n3. Testing Default Configuration...")
    try:
        # Remove app_infra.json to test default fallback
        if os.path.exists("frontend/app_infra.json"):
            os.remove("frontend/app_infra.json")
        
        config = get_use_case_config()
        print(f"✅ Default config: {config}")
        
        expected = {
            "use_cases": [],
            "use_case_filter_enabled": True
        }
        
        if config == expected:
            print("✅ Default configuration working correctly")
        else:
            print(f"❌ Default configuration failed. Expected: {expected}, Got: {config}")
            
    except Exception as e:
        print(f"❌ Default configuration test failed: {str(e)}")
    
    # Test 4: API Endpoint Logic
    print("\n4. Testing API Endpoint Logic...")
    try:
        from utils.resources import get_use_case_config
        
        # Test with use cases configured
        os.environ["USE_CASES"] = '["credit_risk_modeling"]'
        os.environ["USE_CASE_FILTER_ENABLED"] = "true"
        
        config = get_use_case_config()
        
        # Simulate the API endpoint logic
        use_cases_list = None
        if config.get("use_case_filter_enabled", True):
            configured_use_cases = config.get("use_cases", [])
            if configured_use_cases:
                use_cases_list = configured_use_cases
        
        print(f"✅ API logic result: use_cases_list = {use_cases_list}")
        
        if use_cases_list == ["credit_risk_modeling"]:
            print("✅ API endpoint logic working correctly")
        else:
            print(f"❌ API endpoint logic failed. Expected: ['credit_risk_modeling'], Got: {use_cases_list}")
            
    except Exception as e:
        print(f"❌ API endpoint logic test failed: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Use Case Configuration Test Complete")

if __name__ == "__main__":
    test_use_case_config() 