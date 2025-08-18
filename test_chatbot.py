#!/usr/bin/env python3
"""
Test script for the improved Krishi Mitra chatbot
"""

import requests
import json

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER_ID = "test_user_123"

def test_weather_query():
    """Test weather queries"""
    print("Testing weather queries...")
    
    queries = [
        "Will it rain tomorrow?",
        "What's the temperature in Jaipur?",
        "How's the weather in Delhi?",
        "Is it going to rain in Mumbai?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            response = requests.post(f"{BASE_URL}/ask", json={
                "user_id": TEST_USER_ID,
                "query": query
            })
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data.get('answer', 'No answer')}")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_market_query():
    """Test market price queries"""
    print("\n\nTesting market price queries...")
    
    queries = [
        "What's the price of wheat in Jaipur?",
        "How much does rice cost in Delhi?",
        "What are the market prices in Mumbai?",
        "Price of potatoes in Bangalore"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            response = requests.post(f"{BASE_URL}/ask", json={
                "user_id": TEST_USER_ID,
                "query": query
            })
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data.get('answer', 'No answer')}")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_general_query():
    """Test general agricultural queries"""
    print("\n\nTesting general agricultural queries...")
    
    queries = [
        "What crops grow well in Rajasthan?",
        "How to improve soil fertility?",
        "Best time to plant wheat?",
        "What are the benefits of organic farming?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            response = requests.post(f"{BASE_URL}/ask", json={
                "user_id": TEST_USER_ID,
                "query": query
            })
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data.get('answer', 'No answer')}")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def main():
    """Run all tests"""
    print("🚀 Testing Improved Krishi Mitra Chatbot")
    print("=" * 50)
    
    try:
        # Test if server is running
        response = requests.get(f"{BASE_URL}/status?user_id={TEST_USER_ID}")
        if response.status_code != 200:
            print("❌ Server not responding. Make sure to run: python main.py")
            return
        
        print("✅ Server is running")
        
        # Run tests
        test_weather_query()
        test_market_query()
        test_general_query()
        
        print("\n🎉 All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure to run: python main.py")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
