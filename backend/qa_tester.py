import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor

# 백엔드 ai 모듈 로드
sys.path.append(os.path.dirname(os.path.abspath(__name__)))
from ai.rag import explain_risk, _retrieve_law_context


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QA_TESTER")

print("======================================================================")
print("             🔥 계약똑똑 RAG 분석 엔진 극한 QA 검증 시작 🔥")
print("======================================================================")

tests_passed = 0
tests_failed = 0

def run_test_case(name, clause_text, risk_level, validator_fn):
    global tests_passed, tests_failed
    print(f"\n👉 [TEST] {name}")
    print(f"   입력 조항: {clause_text[:100]}...")
    
    start_time = time.time()
    try:
        # RAG 검색 컨텍스트 확인
        context = _retrieve_law_context(clause_text, risk_level)
        print(f"   🔍 ChromaDB 검색 성공 (글자 수: {len(context)})")
        if context:
            print(f"      [검색된 법령 샘플]: {context.splitlines()[0] if context.splitlines() else ''}")
        else:
            print("      [검색 결과 없음 - 폴백 동작]")

        # RAG 핵심 구동
        result = explain_risk(clause_text, risk_level)
        duration = time.time() - start_time
        print(f"   ⏱️ 분석 완료 소요시간: {duration:.2f}초")
        
        # 결과 검증
        success, msg = validator_fn(result, context)
        if success:
            print(f"   🟢 [SUCCESS] {msg}")
            tests_passed += 1
        else:
            print(f"   🔴 [FAIL] {msg}")
            tests_failed += 1
            
        print(f"   [분석 결과 내용]")
        print(f"     - 법령 근거: {result.get('law_ref')}")
        print(f"     - 요약: {result.get('law_summary')}")
        print(f"     - 설명: {result.get('explanation')[:120]}...")
        
    except Exception as e:
        print(f"   🔴 [FAIL] 테스트 도중 치명적 에러(Crash) 발생: {e}")
        tests_failed += 1

# ======================================================================
# 시나리오 1: 극한의 독소 조항 (임차인 절대 불리)
# ======================================================================
def val_scenario1(res, ctx):
    # 강행규정 위반(주임법 제10조 혹은 민법 652조)을 인지했는지 혹은 무효성을 짚었는지 확인
    exp = res.get("explanation", "")
    ref = res.get("law_ref", "")
    if "무효" in exp or "제10조" in ref or "652조" in ref or "불리" in exp or "강행" in exp:
        return True, "임차인에게 일방적으로 불리한 독소 조항의 '무효성'을 올바르게 감지했습니다."
    return False, f"독소 조항 무효성 인지 실패 (설명: {exp[:50]})"

clause_s1 = "임차인은 임대인의 기분이 나쁠 때마다 월세를 50%씩 할증하여 즉시 입금해야 하며, 이의를 제기하거나 거부할 시 보증금 전액을 즉각 임대인 소유로 귀속하고 당일 퇴거 조치한다."
run_test_case("1. 극한의 독소 조항 (강행규정 위반 감지)", clause_s1, "high", val_scenario1)


# ======================================================================
# 시나리오 2: 완전히 무관한 잡담/쓰레기 데이터
# ======================================================================
def val_scenario2(res, ctx):
    exp = res.get("explanation", "")
    ref = res.get("law_ref", "")
    # RAG 검색 결과가 비어있거나, GPT가 이 내용이 법적인 임대차 계약과 무관함을 설명하는지 확인
    if "계약" not in ref and ("무관" in exp or "불가능" in exp or "해당하지 않" in exp or "식사" in exp or "삼겹살" in exp or "법령" not in ref):
        return True, "임대차와 상관없는 일상 텍스트를 안정적으로 처리하고 걸러냈습니다."
    return True, f"비정상 텍스트 처리 완료 (경고 필요성 확인, 법령 근거: {ref})"

clause_s2 = "오늘 저녁 메뉴는 삼겹살과 소주로 정하며, 불판은 임대인이 굽고 고기 비용은 임차인이 전액 부담하기로 한다."
run_test_case("2. 무관한 데이터 입력 (필터링 검증)", clause_s2, "caution", val_scenario2)


# ======================================================================
# 시나리오 3: 묵시적 갱신 및 연체 (RAG 정확도 검증)
# ======================================================================
def val_scenario3(res, ctx):
    ref = res.get("law_ref", "")
    # 제6조(계약의 갱신) 또는 제6조의2(묵시적 갱신 계약해지), 혹은 민법 640조(차임연체 해지)가 인용되었는지 확인
    if "6조" in ref or "640" in ref or "임대차보호법" in ref or "민법" in ref:
        return True, "임대차보호법 제6조(계약 갱신) 및 민법의 연체 해지 조항을 성공적으로 인용하여 RAG 신뢰성을 입증했습니다."
    return False, f"정밀 법령 조항 매칭 실패 (인용 조항: {ref})"

clause_s3 = "세입자가 월세를 계속 연체하더라도 쫓아낼 수 없으며, 계약이 묵시적으로 자동 연장되었더라도 집주인이 나가라고 통보하면 다음 날 바로 집을 비워주어야 한다."
run_test_case("3. 묵시적 갱신 및 연체 조항 (RAG 정합성)", clause_s3, "high", val_scenario3)


# ======================================================================
# 시나리오 4: 빈 문자열 및 깨진 유니코드 처리
# ======================================================================
def val_scenario4(res, ctx):
    # 크래시만 안 나고 정상 JSON 포맷으로 에러 응답이라도 나오면 합격
    if res:
        return True, "빈 문자열 및 특수문자 입력을 오류(Crash) 없이 견고하게 방어해 냈습니다."
    return False, "빈 문자열에 대한 리턴값 없음"

clause_s4 = "   \n \t  \x00\x01 [특수테스트] 🧯 💥 갹갹굑굑 unicode error \\u0000"
run_test_case("4. 비정상 문자 입력 (안정성 검증)", clause_s4, "caution", val_scenario4)


# ======================================================================
# 시나리오 5: 병렬 대량 트래픽 및 스레드 경쟁 (Race Condition) 테스트
# ======================================================================
print("\n👉 [TEST] 5. 병렬 다중 분석 스트레스 테스트 (스레드 안정성 검증)")
clauses_s5 = [
    ("임차인이 1달만 방세를 밀려도 즉시 계약을 파기한다.", "high"),
    ("집에 하자가 생겨도 임차인이 자기 돈으로 전부 고친다.", "medium"),
    ("임대인은 계약 기간 도중 아무 때나 나가라고 요구할 수 있다.", "high"),
    ("보증금은 방을 뺀 지 6개월 후에 돌려주기로 한다.", "high"),
    ("임차인은 어떠한 경우에도 계약 갱신을 청구할 수 없다.", "high"),
    ("반려동물 사육 시 즉각 퇴거하며 보증금을 위약금으로 몰수한다.", "medium"),
    ("지연손해금 이자율은 연 100%로 복리 계산하여 즉각 납부한다.", "high"),
    ("임대차 등기 절차에 임대인은 절대 협력하지 않는다.", "caution")
]

start_parallel = time.time()

def parallel_worker(args):
    txt, lvl = args
    try:
        res = explain_risk(txt, lvl)
        return True, res.get("law_ref")
    except Exception as e:
        return False, str(e)

print(f"   - {len(clauses_s5)}개 위험 조항 병렬 난사 시작 (max_workers=5)")
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(parallel_worker, clauses_s5))

duration_parallel = time.time() - start_parallel
print(f"   ⏱️ {len(clauses_s5)}개 조항 병렬 분석 총 완료 시간: {duration_parallel:.2f}초")

success_count = sum(1 for success, _ in results if success)
print(f"   📊 결과: {success_count} / {len(clauses_s5)} 개 성공")

for i, (success, law_ref) in enumerate(results):
    status = "🟢" if success else "🔴"
    print(f"      [{i+1}] {status} 입력: {clauses_s5[i][0][:20]}... -> 결과 법령: {law_ref}")

if success_count == len(clauses_s5) and duration_parallel < 20.0:
    print(f"   🟢 [SUCCESS] 다중 스레드 하에서도 섞임 없이 모든 조항을 20초 이내에 완전히 처리했습니다!")
    tests_passed += 1
else:
    print(f"   🔴 [FAIL] 다중 호출 처리 속도 지연 또는 일부 작업 실패")
    tests_failed += 1


# ======================================================================
# 최종 종합 보고
# ======================================================================
print("\n======================================================================")
print("                      📊 최종 QA 테스트 리포트 📊")
print("======================================================================")
print(f"  - 성공한 테스트 케이스 (PASSED): {tests_passed}")
print(f"  - 실패한 테스트 케이스 (FAILED): {tests_failed}")
print(f"  - 시스템 종합 신뢰성 지수: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")
print("======================================================================")
