#!/bin/bash

BASE_URL="https://www.ukteawallet.com"
CARD_ID="04E7C58A0B6280"
MACHINE_ID="UK_0007"

echo "🔐 Testing UK Tea Wallet API"
echo "=============================="

# Step 1
echo -e "\n1️⃣ Starting authentication..."
RESPONSE=$(curl -s -X POST $BASE_URL/api/rfid/auth/start \
  -H "Content-Type: application/json" \
  -d "{
    \"cardId\": \"$CARD_ID\",
    \"keyNumber\": 0,
    \"machineId\": \"$MACHINE_ID\"
  }")

echo "$RESPONSE" | jq

# Extract sessionId
SESSION_ID=$(echo "$RESPONSE" | jq -r '.sessionId')

if [ "$SESSION_ID" != "null" ]; then
    echo "✅ Session ID: $SESSION_ID"
else
    echo "❌ Failed to get session ID"
fi