import requests
import json
import time
from typing import Optional, List
from indexao_core.config import LLMConfig

class KeyState:
    def __init__(self, key: str, rpm: int, daily_limit: int):
        self.key = key
        self.rpm = rpm
        self.daily_limit = daily_limit
        self.last_request_time = 0
        self.request_count_today = 0
        # Min interval per key to safety buffer (slightly more than strict math to avoid jitter)
        # Increase safety buffer to avoid burst limits
        self.min_interval = (60.0 / rpm) * 1.1 if rpm > 0 else 0
        self.cooldown_until = 0

    def time_until_ready(self) -> float:
        """Returns seconds to wait before this key can be used."""
        now = time.time()
        
        # Check explicit cooldown first
        if self.cooldown_until > now:
            return self.cooldown_until - now
            
        elapsed = now - self.last_request_time
        return max(0, self.min_interval - elapsed)

class GeminiAdapter:
    def __init__(self, config: LLMConfig):
        self.model = config.model
        
        # Initialize Keys
        raw_keys = []
        if config.api_keys:
            raw_keys.extend(config.api_keys)
        elif config.api_key:
            raw_keys.append(config.api_key)
            
        # Clean duplicates and empty
        raw_keys = list(set([k for k in raw_keys if k.strip()]))
        
        if not raw_keys:
            print("⚠️ No API Keys configured for Gemini.")
            self.keys = []
        else:
            print(f"ℹ️  Gemini Adapter initialized with {len(raw_keys)} API keys.")
            self.keys = [KeyState(k, config.rpm, config.daily_limit) for k in raw_keys]

        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.current_key_idx = 0

    def _get_best_key(self) -> tuple[Optional[KeyState], float]:
        """
        Round-robin selection of the next available key.
        Returns (Selected KeyState, Seconds to Wait)
        """
        if not self.keys:
            return None, 0

        # 1. Try to find a key ready NOW (Round Robin)
        start_idx = self.current_key_idx
        min_wait = float('inf')
        best_key_idx = -1
        available_keys_count = 0

        for i in range(len(self.keys)):
            # Rotate checking
            idx = (start_idx + i) % len(self.keys)
            key_state = self.keys[idx]

            # Skip exhausted keys
            if key_state.request_count_today >= key_state.daily_limit:
                continue

            # Skip explicitly cooled down keys (429) unless all keys are cooling down
            if key_state.cooldown_until > time.time():
                continue
                
            available_keys_count += 1

            wait = key_state.time_until_ready()
            
            # If ready immediately, take it
            if wait == 0:
                self.current_key_idx = (idx + 1) % len(self.keys)
                return key_state, 0
            
            # Otherwise track best candidate
            if wait < min_wait:
                min_wait = wait
                best_key_idx = idx

        # No key ready immediately. 
        
        # Scenario A: We found a valid key that is just throttled by RPM
        if best_key_idx != -1:
            self.current_key_idx = (best_key_idx + 1) % len(self.keys)
            return self.keys[best_key_idx], min_wait
            
        # Scenario B: No valid key found. Check if any are in temporary cooldown (429)
        # and pick the one recovering soonest.
        min_cooldown = float('inf')
        cooldown_key_idx = -1
        
        for i, k in enumerate(self.keys):
            if k.request_count_today < k.daily_limit and k.cooldown_until > time.time():
                wait = k.cooldown_until - time.time()
                if wait < min_cooldown:
                    min_cooldown = wait
                    cooldown_key_idx = i
        
        if cooldown_key_idx != -1:
             self.current_key_idx = (cooldown_key_idx + 1) % len(self.keys)
             # Return this key but tell the caller to wait the full cooldown
             return self.keys[cooldown_key_idx], min_cooldown

        # Scenario C: Everyone is exhausted (daily limit)
        return None, 0

        # Should not reach here typically
        return None, 60.0

    def translate(self, text: str, target_lang: str = "fr") -> Optional[str]:
        if not text.strip():
            return None
        
        if not self.keys:
            return None

        # Robust prompt
        prompt = f"""
        Role: Expert Translator & Document Formatter.
        Task: Translate the following text into French.
        
        CRITICAL INSTRUCTIONS:
        1. Keep the exact visual structure of the original document using Markdown.
        2. Use '# Title' for main headers and '## Subtitle' for sections.
        3. Use '**Bold**' for keys/labels (e.g. '**Name**:', '**Date**:').
        4. Use lists (- item) for enumerations.
        5. Insert '---' markdown separators between distinct sections to improve readability.
        6. Output ONLY the translated Markdown. No intro/outro text.
        
        Text to translate:
        {text}
        """
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        # Retry loop (handles network issues + trying other keys on 429)
        # Using a larger retry count to allow cycling through all keys multiple times if needed
        max_retries = len(self.keys) * 2 + 1 if self.keys else 3
        
        for attempt in range(max_retries):
            
            # Select Key
            key_state, wait_time = self._get_best_key()
            
            if not key_state:
                print("⚠️ All API keys have reached their daily limits.")
                return None

            # Enforce Rate Limit for this specific key
            if wait_time > 0:
                print(f"   ⏳ Multi-Key Throttling: waiting {wait_time:.1f}s...", end="", flush=True)
                time.sleep(wait_time)

            # Execution
            try:
                # Construct URL with specific key
                request_url = f"{self.base_url}?key={key_state.key}"
                headers = {'Content-Type': 'application/json'}
                
                # Update counters
                key_state.last_request_time = time.time()
                key_state.request_count_today += 1
                
                # Increased timeout for Free Tier stability and long documents
                # 3193s for 41 files = ~78s/file. 60s is too tight for large contexts.
                response = requests.post(request_url, headers=headers, json=payload, timeout=120)
                
                if response.status_code == 200:
                    data = response.json()
                    try:
                        candidate = data["candidates"][0]
                        translated_text = candidate["content"]["parts"][0]["text"]
                        return translated_text.strip()
                    except (KeyError, IndexError) as e:
                        print(f"❌ Gemini Parse Error: {e}")
                        return None
                
                elif response.status_code == 429:
                    err_text = response.text.lower()
                    if "quota" in err_text or "exhausted" in err_text:
                        print(f"⛔ Key ...{key_state.key[-4:]} hit DAILY QUOTA. Disabling for session.")
                        key_state.request_count_today = key_state.daily_limit + 1
                    else:
                        print(f"⚠️ Key ...{key_state.key[-4:]} hit 429 (Rate Limit). Cooling down 60s...")
                        # Mark this key as cold for 60s
                        key_state.cooldown_until = time.time() + 60
                    continue

                elif response.status_code == 400:
                    # Check for API Key issues to allow failover
                    err_text = response.text.lower()
                    if "api_key" in err_text or "api key" in err_text or "expired" in err_text or "invalid" in err_text:
                        print(f"⚠️ Key ...{key_state.key[-4:]} is INVALID/EXPIRED. Switching key...")
                        # Disable this key for the session
                        key_state.daily_limit = 0 
                        continue
                    else:
                        print(f"❌ API Error ({response.status_code}): {response.text}")
                        return None
                
                else:
                    print(f"❌ API Error ({response.status_code}): {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
                time.sleep(1)
                continue
                
        return None

if __name__ == "__main__":
    # Test
    cfg = LLMConfig(api_key="TEST_KEY_FROM_CONFIG_TO_BE_FILLED", model="gemini-2.0-flash")
    # adapter = GeminiAdapter(cfg)
    # print(adapter.translate("你好，这个是测试。"))
    pass
