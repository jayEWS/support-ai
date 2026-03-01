"""
RAG Evaluation Module - Test RAG system accuracy offline
Uses RAGAS & DeepEval for evaluating:
- Faithfulness: Does answer stick to context?
- Relevance: Is answer relevant to query?
- Ground Truth Comparison: Does it match expected answer?
"""

import os
from typing import List, Optional, Tuple
from dataclasses import dataclass
from app.core.logging import logger

try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, relevance, context_precision
    from datasets import Dataset
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.warning("RAGAS not available - install with: pip install ragas")

try:
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
    from deepeval.test_case import LLMTestCase
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False
    logger.warning("DeepEval not available - install with: pip install deepeval")


@dataclass
class RAGEvalResult:
    """RAG Evaluation Result"""
    query: str
    answer: str
    context: str
    faithfulness_score: Optional[float] = None
    relevance_score: Optional[float] = None
    context_precision_score: Optional[float] = None
    overall_score: Optional[float] = None
    passed: bool = False
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class RAGEvaluator:
    """Evaluate RAG quality using RAGAS & DeepEval"""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.results: List[RAGEvalResult] = []

    def evaluate_with_ragas(
        self,
        queries: List[str],
        contexts: List[List[str]],
        answers: List[str],
        ground_truths: Optional[List[str]] = None
    ) -> List[RAGEvalResult]:
        """
        Evaluate using RAGAS framework
        Returns scores for: faithfulness, relevance, context_precision
        """
        if not RAGAS_AVAILABLE:
            logger.error("RAGAS not available")
            return []

        try:
            # Prepare dataset for RAGAS
            eval_data = {
                "question": queries,
                "answer": answers,
                "contexts": contexts,
            }
            
            if ground_truths:
                eval_data["ground_truth"] = ground_truths

            dataset = Dataset.from_dict(eval_data)

            # Run RAGAS evaluation
            logger.info(f"Running RAGAS evaluation on {len(queries)} samples...")
            results = evaluate(
                dataset,
                metrics=[
                    faithfulness,
                    relevance,
                    context_precision,
                ]
            )

            # Convert to RAGEvalResult
            eval_results = []
            for i, query in enumerate(queries):
                result = RAGEvalResult(
                    query=query,
                    answer=answers[i],
                    context="\n".join(contexts[i]) if i < len(contexts) else "",
                    faithfulness_score=results["faithfulness"][i] if "faithfulness" in results else None,
                    relevance_score=results["relevance"][i] if "relevance" in results else None,
                    context_precision_score=results["context_precision"][i] if "context_precision" in results else None,
                )

                # Calculate overall score
                scores = [
                    result.faithfulness_score,
                    result.relevance_score,
                    result.context_precision_score
                ]
                valid_scores = [s for s in scores if s is not None]
                if valid_scores:
                    result.overall_score = sum(valid_scores) / len(valid_scores)
                    result.passed = result.overall_score >= self.threshold

                eval_results.append(result)

            self.results.extend(eval_results)
            return eval_results

        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            return []

    def evaluate_with_deepeval(
        self,
        queries: List[str],
        answers: List[str],
        contexts: Optional[List[str]] = None,
        ground_truths: Optional[List[str]] = None
    ) -> List[RAGEvalResult]:
        """
        Evaluate using DeepEval framework
        Tests: Answer Relevancy, Faithfulness
        """
        if not DEEPEVAL_AVAILABLE:
            logger.error("DeepEval not available")
            return []

        try:
            logger.info(f"Running DeepEval evaluation on {len(queries)} samples...")
            eval_results = []

            for i, query in enumerate(queries):
                test_case = LLMTestCase(
                    input=query,
                    actual_output=answers[i],
                    expected_output=ground_truths[i] if ground_truths and i < len(ground_truths) else None,
                    context=contexts[i] if contexts and i < len(contexts) else None,
                )

                # Evaluate relevancy
                relevancy_metric = AnswerRelevancyMetric(threshold=self.threshold)
                relevancy_metric.measure(test_case)
                relevancy_passed = relevancy_metric.is_successful()
                relevancy_score = relevancy_metric.score

                # Evaluate faithfulness
                faithfulness_metric = FaithfulnessMetric(threshold=self.threshold)
                faithfulness_metric.measure(test_case)
                faithfulness_passed = faithfulness_metric.is_successful()
                faithfulness_score = faithfulness_metric.score

                result = RAGEvalResult(
                    query=query,
                    answer=answers[i],
                    context=contexts[i] if contexts and i < len(contexts) else "",
                    relevance_score=relevancy_score,
                    faithfulness_score=faithfulness_score,
                    overall_score=(relevancy_score + faithfulness_score) / 2,
                    passed=relevancy_passed and faithfulness_passed,
                )

                if not result.passed:
                    if not relevancy_passed:
                        result.issues.append(f"Answer not relevant (score: {relevancy_score})")
                    if not faithfulness_passed:
                        result.issues.append(f"Answer not faithful to context (score: {faithfulness_score})")

                eval_results.append(result)

            self.results.extend(eval_results)
            return eval_results

        except Exception as e:
            logger.error(f"DeepEval evaluation failed: {e}")
            return []

    def get_summary(self) -> dict:
        """Get evaluation summary"""
        if not self.results:
            return {"total": 0, "passed": 0, "passed_rate": 0}

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)

        avg_faithfulness = sum(
            r.faithfulness_score for r in self.results if r.faithfulness_score
        ) / sum(1 for r in self.results if r.faithfulness_score) if any(r.faithfulness_score for r in self.results) else None

        avg_relevance = sum(
            r.relevance_score for r in self.results if r.relevance_score
        ) / sum(1 for r in self.results if r.relevance_score) if any(r.relevance_score for r in self.results) else None

        return {
            "total": total,
            "passed": passed,
            "passed_rate": f"{(passed / total * 100):.1f}%",
            "avg_faithfulness": f"{avg_faithfulness:.2f}" if avg_faithfulness else "N/A",
            "avg_relevance": f"{avg_relevance:.2f}" if avg_relevance else "N/A",
            "issues": [
                {"query": r.query, "issues": r.issues}
                for r in self.results if r.issues
            ]
        }

    def print_report(self):
        """Print evaluation report"""
        summary = self.get_summary()
        logger.info(f"""
╔════════════════════════════════════════╗
║  RAG EVALUATION REPORT                 ║
╠════════════════════════════════════════╣
║ Total Tests:      {summary['total']:<20}║
║ Passed:           {summary['passed']:<20}║
║ Pass Rate:        {summary['passed_rate']:<18}║
║ Avg Faithfulness: {str(summary['avg_faithfulness']):<18}║
║ Avg Relevance:    {str(summary['avg_relevance']):<18}║
╚════════════════════════════════════════╝
        """)

        if summary['issues']:
            logger.warning(f"Found {len(summary['issues'])} issues:")
            for issue in summary['issues']:
                logger.warning(f"  Q: {issue['query']}")
                for problem in issue['issues']:
                    logger.warning(f"    - {problem}")


# Example usage
if __name__ == "__main__":
    # Sample test cases
    queries = [
        "How to enable notifications?",
        "What is the return policy?",
    ]
    
    contexts = [
        ["Settings > Notifications > Enable all"],
        ["Returns accepted within 30 days with receipt"],
    ]
    
    answers = [
        "You can enable notifications in Settings menu under Notifications section.",
        "We accept returns within 30 days if you have the receipt.",
    ]
    
    ground_truths = [
        "Go to Settings > Notifications to enable",
        "30 day return policy with receipt required",
    ]

    evaluator = RAGEvaluator(threshold=0.6)
    
    # Evaluate using DeepEval
    if DEEPEVAL_AVAILABLE:
        results = evaluator.evaluate_with_deepeval(
            queries=queries,
            answers=answers,
            contexts=contexts,
            ground_truths=ground_truths
        )
        evaluator.print_report()
