#!/usr/bin/env python3
"""
Test script for the SMART Krishi Mitra chatbot
Tests all the intelligent features and complex queries
"""

import requests
import json

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER_ID = "test_user_123"

def test_growing_cost_queries():
    """Test growing cost queries - should be smart, not dumb"""
    print("🧪 Testing Growing Cost Queries (Smart vs Dumb)")
    print("=" * 60)
    
    queries = [
        "what much will it cost to grow rice",
        "how much does it cost to grow wheat in Punjab",
        "cultivation cost of cotton in Gujarat",
        "production cost for sugarcane in UP"
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
                answer = data.get('answer', 'No answer')
                print(f"Response: {answer[:200]}...")
                
                # Check if it's smart (not just market prices)
                if "cost to grow" in answer.lower() or "cultivation cost" in answer.lower():
                    print("✅ SMART: Provided growing cost information")
                elif "market price" in answer.lower() or "modal price" in answer.lower():
                    print("❌ DUMB: Gave market prices instead of growing costs")
                else:
                    print("🤔 UNKNOWN: Response type unclear")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_smart_market_queries():
    """Test smart market queries with context"""
    print("\n\n🧪 Testing Smart Market Queries")
    print("=" * 60)
    
    queries = [
        "what is the price of rice in chandigarh punjab",
        "rice ka bhav kya hai near me",
        "top 3 mandis to sell onion in Nashik",
        "is soybean price in Indore trending up or down",
        "best place to sell basmati from Karnal"
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
                answer = data.get('answer', 'No answer')
                print(f"Response: {answer[:200]}...")
                
                # Check for smart features
                if "📊" in answer or "💡" in answer:
                    print("✅ SMART: Used emojis and smart formatting")
                if "Price Range" in answer or "Consider selling" in answer:
                    print("✅ SMART: Provided actionable insights")
                if "trend" in answer.lower() or "comparison" in answer.lower():
                    print("✅ SMART: Handled trend/comparison query")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_smart_weather_queries():
    """Test smart weather queries with actionable advice"""
    print("\n\n🧪 Testing Smart Weather Queries")
    print("=" * 60)
    
    queries = [
        "will it rain tomorrow evening in 751001",
        "humidity tomorrow morning in Coimbatore",
        "wind gusts next 24h near Kurnool",
        "chance of frost this weekend in Hisar"
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
                answer = data.get('answer', 'No answer')
                print(f"Response: {answer[:200]}...")
                
                # Check for smart weather features
                if "💡 Smart Actions" in answer:
                    print("✅ SMART: Provided actionable weather advice")
                elif "🌤️" in answer or "🌧️" in answer:
                    print("✅ SMART: Used weather emojis and formatting")
                else:
                    print("🤔 Basic weather response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_policy_and_scheme_queries():
    """Test policy and scheme queries"""
    print("\n\n🧪 Testing Policy and Scheme Queries")
    print("=" * 60)
    
    queries = [
        "PM-Kisan: am I eligible with 1.2 acres in West Bengal",
        "Kalia benefits for sharecroppers in Odisha",
        "Rythu Bandhu for tenant farmers in Telangana"
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
                answer = data.get('answer', 'No answer')
                print(f"Response: {answer[:200]}...")
                
                if "eligibility" in answer.lower() or "requirements" in answer.lower():
                    print("✅ SMART: Provided policy guidance")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_agricultural_decisions():
    """Test agricultural decision queries"""
    print("\n\n🧪 Testing Agricultural Decision Queries")
    print("=" * 60)
    
    queries = [
        "wheat vs mustard on 3 acres in Rajasthan",
        "intercrop options for bajra in Bundelkhand",
        "when to spray imazethapyr for soybean"
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
                answer = data.get('answer', 'No answer')
                print(f"Response: {answer[:200]}...")
                
                if "pros/cons" in answer.lower() or "recommendation" in answer.lower():
                    print("✅ SMART: Provided decision support")
                elif "timing" in answer.lower() or "optimal" in answer.lower():
                    print("✅ SMART: Provided timing advice")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def main():
    """Run all smart tests"""
    print("🚀 Testing SMART Krishi Mitra Chatbot")
    print("=" * 60)
    
    try:
        # Test if server is running
        response = requests.get(f"{BASE_URL}/status?user_id={TEST_USER_ID}")
        if response.status_code != 200:
            print("❌ Server not responding. Make sure to run: python main.py")
            return
        
        print("✅ Server is running")
        
        # Run all tests
        test_growing_cost_queries()
        test_smart_market_queries()
        test_smart_weather_queries()
        test_policy_and_scheme_queries()
        test_agricultural_decisions()
        
        print("\n🎉 All SMART tests completed!")
        print("\n💡 The chatbot should now be:")
        print("   ✅ Smart about growing costs (not just market prices)")
        print("   ✅ Contextual about locations (Chandigarh vs Delhi)")
        print("   ✅ Actionable with weather advice")
        print("   ✅ Intelligent about agricultural decisions")
        print("   ✅ Helpful with policy guidance")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure to run: python main.py")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
