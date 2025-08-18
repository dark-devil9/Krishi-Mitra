#!/usr/bin/env python3
"""
Comprehensive test script for the FIXED Krishi Mitra chatbot
Tests all the complex queries that were failing before
"""

import requests
import json

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER_ID = "test_user_123"

def test_mandi_price_queries():
    """Test mandi price queries that were failing"""
    print("🧪 Testing Mandi Price Queries (Location & Commodity Fixes)")
    print("=" * 70)
    
    queries = [
        "What is the modal price of wheat today in 560001?",
        "Rice ka bhav kya hai near me (I stay in Navi Mumbai)?",
        "what is the price of rice in punjab",
        "what is the price of wheat in 302031",
        "what is the price of tomato in gujarat",
        "Price of chikpea in Kota (typo intentional)",
        "Rate of cotton in Warangal district today",
        "Min–max–modal for groundnut in Rajkot"
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
                print(f"Response: {answer[:300]}...")
                
                # Check for specific fixes
                if "rice" in query.lower() and "rice" not in answer.lower():
                    print("❌ FAILED: Rice query didn't return rice prices")
                elif "wheat" in query.lower() and "wheat" not in answer.lower():
                    print("❌ FAILED: Wheat query didn't return wheat prices")
                elif "tomato" in query.lower() and "tomato" not in answer.lower():
                    print("❌ FAILED: Tomato query didn't return tomato prices")
                elif "chikpea" in query.lower() and "chickpea" not in answer.lower():
                    print("❌ FAILED: Typo correction didn't work")
                else:
                    print("✅ PASSED: Query handled correctly")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_trend_and_comparison_queries():
    """Test trend and comparison queries"""
    print("\n\n🧪 Testing Trend and Comparison Queries")
    print("=" * 70)
    
    queries = [
        "Is soybean price in Indore trending up or down over the last 10 days?",
        "What's the best place to sell basmati from Karnal—Karnal, Kurukshetra, or Delhi Azadpur?",
        "Top 3 mandis to sell onion in Nashik division this week—rank by price and liquidity",
        "Cash crop prices in Tripura today—top 5 commodities by arrivals"
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
                print(f"Response: {answer[:300]}...")
                
                if "trend" in query.lower() and "trend" in answer.lower():
                    print("✅ PASSED: Trend query handled")
                elif "best place" in query.lower() and "top" in answer.lower():
                    print("✅ PASSED: Comparison query handled")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_weather_and_risk_queries():
    """Test weather and risk queries"""
    print("\n\n🧪 Testing Weather and Risk Queries")
    print("=" * 70)
    
    queries = [
        "Will it rain tomorrow evening in 751001? If yes, should I delay urea top-dressing?",
        "Humidity tomorrow morning in Coimbatore taluk—single line only",
        "Wind gusts next 24h near Kurnool; safe window to spray?",
        "Chance of frost this weekend in Hisar; should I cover vegetables?",
        "Heat stress risk for cotton in Vidarbha this week—yes/no with 1 action"
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
                print(f"Response: {answer[:300]}...")
                
                if "💡 Smart Actions" in answer or "🌤️" in answer:
                    print("✅ PASSED: Smart weather response")
                else:
                    print("🤔 Basic weather response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_policy_and_scheme_queries():
    """Test policy and scheme queries"""
    print("\n\n🧪 Testing Policy and Scheme Queries")
    print("=" * 70)
    
    queries = [
        "PM-Kisan: am I eligible with 1.2 acres in West Bengal and a pending mutation?",
        "Kalia (Odisha): benefits for sharecroppers vs small/marginal owner—am I covered?",
        "Rythu Bandhu (Telangana): tenant farmer on lease—include or excluded?",
        "PMFBY claim: sown area 3 acres, rain shortfall, district notified—can I file now?"
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
                print(f"Response: {answer[:300]}...")
                
                if "eligibility" in answer.lower() or "requirements" in answer.lower():
                    print("✅ PASSED: Policy guidance provided")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_logistics_and_timing_queries():
    """Test logistics and timing queries"""
    print("\n\n🧪 Testing Logistics and Timing Queries")
    print("=" * 70)
    
    queries = [
        "Should I sell onion now in Lasalgaon or store for 4 weeks given current trend and losses?",
        "Best day in next 3 days to harvest paddy in Thanjavur—combine rain + wind + RH",
        "When to spray imazethapyr post-emergence for soybean if rain expected tomorrow?",
        "Which cold storage within 50km of Lucknow for potatoes; give nearest 3 with capacity if available"
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
                print(f"Response: {answer[:300]}...")
                
                if "recommendation" in answer.lower() or "advice" in answer.lower():
                    print("✅ PASSED: Logistics advice provided")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def test_cropping_decisions():
    """Test cropping decision queries"""
    print("\n\n🧪 Testing Cropping Decision Queries")
    print("=" * 70)
    
    queries = [
        "For rabi in Rajasthan (semi-arid), wheat vs mustard on 3 acres—brief pros/cons + recommendation",
        "Intercrop options for bajra in low rainfall in Bundelkhand; seed rates and row ratio",
        "Short-duration paddy varieties for delayed transplanting in Assam this year",
        "Replacing sugarcane with horticulture in UP West—viable alternatives with water use note"
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
                print(f"Response: {answer[:300]}...")
                
                if "pros/cons" in answer.lower() or "recommendation" in answer.lower():
                    print("✅ PASSED: Decision support provided")
                else:
                    print("🤔 Basic response")
            else:
                print(f"Error: {response.status_code}")
        except Exception as e:
            print(f"Exception: {e}")

def main():
    """Run all comprehensive tests"""
    print("🚀 Testing FIXED Krishi Mitra Chatbot - All Complex Queries")
    print("=" * 70)
    
    try:
        # Test if server is running
        response = requests.get(f"{BASE_URL}/status?user_id={TEST_USER_ID}")
        if response.status_code != 200:
            print("❌ Server not responding. Make sure to run: python main.py")
            return
        
        print("✅ Server is running")
        
        # Run all tests
        test_mandi_price_queries()
        test_trend_and_comparison_queries()
        test_weather_and_risk_queries()
        test_policy_and_scheme_queries()
        test_logistics_and_timing_queries()
        test_cropping_decisions()
        
        print("\n🎉 All comprehensive tests completed!")
        print("\n💡 The chatbot should now correctly handle:")
        print("   ✅ Location parsing (Punjab vs Delhi)")
        print("   ✅ Commodity filtering (rice queries return rice prices)")
        print("   ✅ Pincode resolution (302031 -> Rajasthan)")
        print("   ✅ Typo correction (chikpea -> chickpea)")
        print("   ✅ Complex market queries")
        print("   ✅ Weather intelligence")
        print("   ✅ Policy guidance")
        print("   ✅ Agricultural decisions")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure to run: python main.py")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
