#!/usr/bin/env python3
import json
import hashlib
import math
import random
import sys
from collections import Counter, defaultdict

FIELD_LABELS = {
    "business_segment": "Segmento",
    "lifecycle_stage": "Etapa",
    "preferred_channel": "Canal",
    "interest": "Interesse",
    "city": "Cidade",
    "state": "Estado",
    "region": "Região",
    "country": "País",
    "phone_subregion": "Sub-região do telefone",
}

VALUE_LABELS = {
    "active": "Ativos",
    "inactive": "Inativos",
    "lead": "Leads",
    "customer": "Clientes",
    "prospect": "Prospects",
    "whatsapp": "WhatsApp",
    "email": "Email",
    "sms": "SMS",
    "cold": "frio",
    "warm": "morno",
    "hot": "quente",
}

TERM_STOPWORDS = {
    "active",
    "inactive",
    "lead",
    "customer",
    "prospect",
    "channel",
    "preferred",
    "whatsapp",
    "email",
    "engagement",
    "cold",
    "warm",
    "hot",
    "business",
    "profile",
    "name",
    "has",
    "true",
    "false",
    "unknown",
    "contact",
    "contato",
    "cliente",
    "clientes",
    "empresa",
    "empresas",
    "servico",
    "servicos",
    "atendimento",
}


def tokenize(values):
    tokens = []
    for value in values:
        if not value:
            continue
        current = []
        for char in str(value).lower():
            if char.isalnum():
                current.append(char)
            else:
                if len(current) >= 3:
                    tokens.append("".join(current))
                current = []
        if len(current) >= 3:
            tokens.append("".join(current))
    return tokens


def hash_bucket(token, dims):
    return int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % dims


def build_vector(row, hashed_dims=32):
    features = row.get("features", {})
    numeric = features.get("numeric", {})
    categorical = features.get("categorical", {})
    tags = features.get("tags", [])
    terms = features.get("text_terms", [])
    embedding = features.get("embedding_vector", [])

    vector = [
        float(numeric.get("engagement_score", 0.0)) / 100.0,
        float(numeric.get("messages_count", 0.0)) / 25.0,
        float(numeric.get("has_whatsapp", 0.0)),
        float(numeric.get("pending_reviews_count", 0.0)) / 10.0,
        float(numeric.get("active_tags_count", 0.0)) / 10.0,
        min(float(numeric.get("days_since_last_interaction", 365.0)) / 365.0, 1.0),
    ]

    hashed = [0.0] * hashed_dims
    categorical_tokens = [f"{key}:{value}" for key, value in categorical.items() if value and value != "unknown"]
    for token in tokenize(categorical_tokens + tags + terms[:8]):
        hashed[hash_bucket(token, hashed_dims)] += 1.0

    if embedding:
        vector.extend([float(value) for value in embedding])

    vector.extend(hashed)
    norm = math.sqrt(sum(item * item for item in vector))
    if norm > 0:
        vector = [round(item / norm, 8) for item in vector]

    return vector


def readable_value(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw == "unknown":
        return None
    return VALUE_LABELS.get(raw, raw.replace("_", " ").title())


def engagement_bucket(score):
    if score < 35:
        return "frio"
    if score < 70:
        return "morno"
    return "quente"


def readable_tag(tag):
    raw = str(tag).strip()
    labels = {
        "engagement.cold": "Engajamento frio",
        "engagement.warm": "Engajamento morno",
        "engagement.hot": "Engajamento quente",
        "channel.whatsapp": "Canal WhatsApp",
        "canal.whatsapp": "Canal WhatsApp",
        "possui.whatsapp": "Possui WhatsApp",
    }
    return labels.get(raw, raw.replace(".", " ").replace("_", " ").title())


def clean_terms(terms, limit=6):
    cleaned = []
    for term, _ in Counter(terms).most_common():
        normalized = str(term).strip().lower()
        if len(normalized) < 3 or normalized in TERM_STOPWORDS:
            continue
        if normalized not in cleaned:
            cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def criteria_from_dominant(dominant, tags, keywords, avg_engagement):
    criteria = []
    priority_fields = ["business_segment", "lifecycle_stage", "preferred_channel", "interest", "city", "state"]

    for field in priority_fields:
        value = readable_value(dominant.get(field))
        if value:
            criteria.append({"label": FIELD_LABELS.get(field, field), "value": value})

    if avg_engagement is not None:
        criteria.append({"label": "Engajamento médio", "value": f"{avg_engagement:.0f} ({engagement_bucket(avg_engagement)})"})

    if tags:
        criteria.append({"label": "Tags frequentes", "value": ", ".join(readable_tag(tag) for tag in tags[:3])})

    if keywords:
        criteria.append({"label": "Termos diferenciais", "value": ", ".join(keywords[:3])})

    return criteria[:6]


def build_label(dominant, keywords, avg_engagement):
    segment = readable_value(dominant.get("business_segment"))
    stage = readable_value(dominant.get("lifecycle_stage"))
    channel = readable_value(dominant.get("preferred_channel"))
    engagement = f"Engajamento {engagement_bucket(avg_engagement)}"

    parts = []
    if segment:
        parts.append(segment)
    if stage:
        parts.append(stage)
    if channel and len(parts) < 3:
        parts.append(channel)
    if engagement and len(parts) < 3:
        parts.append(engagement)

    if not parts and keywords:
        parts.append("Termos: " + " / ".join(keyword.title() for keyword in keywords[:2]))

    if len(parts) == 1 and keywords:
        parts.append("Termos: " + " / ".join(keyword.title() for keyword in keywords[:2]))

    return " · ".join(parts) if parts else "Cluster sugerido"


def build_reason(criteria, keywords):
    anchors = [f"{item['label'].lower()} {item['value']}" for item in criteria[:3]]
    reason = "Agrupado principalmente por " + ", ".join(anchors) if anchors else "Agrupado por sinais semelhantes."
    if keywords:
        reason += f". Termos que diferenciam o grupo: {', '.join(keywords[:3])}."
    return reason


def distance(left, right):
    size = min(len(left), len(right))
    if size == 0:
        return 1.0
    return math.sqrt(sum((left[i] - right[i]) ** 2 for i in range(size)))


def mean_vector(vectors):
    if not vectors:
        return []
    size = len(vectors[0])
    totals = [0.0] * size
    for vector in vectors:
        for idx, value in enumerate(vector):
            totals[idx] += value
    return [value / len(vectors) for value in totals]


def choose_k(count, max_clusters):
    if count < 4:
        return 2
    return max(2, min(max_clusters, int(round(math.sqrt(count / 2)))))


def kmeans(rows, max_clusters):
    vectors = [build_vector(row) for row in rows]
    k = choose_k(len(rows), max_clusters)
    random.seed(42)
    centroids = [vectors[idx] for idx in random.sample(range(len(vectors)), k)]

    for _ in range(12):
        assignments = [[] for _ in range(k)]
        for idx, vector in enumerate(vectors):
            nearest = min(range(k), key=lambda centroid_idx: distance(vector, centroids[centroid_idx]))
            assignments[nearest].append(idx)

        new_centroids = []
        for cluster_idx in range(k):
            if assignments[cluster_idx]:
                new_centroids.append(mean_vector([vectors[idx] for idx in assignments[cluster_idx]]))
            else:
                new_centroids.append(centroids[cluster_idx])

        if new_centroids == centroids:
            break
        centroids = new_centroids

    return assignments, centroids, vectors


def summarize_cluster(member_rows):
    categorical = defaultdict(list)
    all_tags = []
    all_terms = []
    engagement_scores = []

    for row in member_rows:
        features = row.get("features", {})
        for key, value in (features.get("categorical", {}) or {}).items():
            if value and value != "unknown":
                categorical[key].append(value)
        all_tags.extend(features.get("tags", []) or [])
        all_terms.extend(features.get("text_terms", []) or [])
        engagement_scores.append(float((features.get("numeric", {}) or {}).get("engagement_score", 0.0)))

    dominant = {
        key: Counter(values).most_common(1)[0][0]
        for key, values in categorical.items()
        if values
    }
    avg_engagement = round(sum(engagement_scores) / max(1, len(engagement_scores)), 2)
    keywords = clean_terms(all_terms, 6)
    tags = [item for item, _ in Counter(all_tags).most_common(4)]
    criteria = criteria_from_dominant(dominant, tags, keywords, avg_engagement)
    label = build_label(dominant, keywords, avg_engagement)

    return {
        "name": label,
        "slug": label.lower().replace(" · ", "-").replace(" / ", "-").replace(" ", "-"),
        "summary": {
            "dominant_segment": dominant.get("business_segment"),
            "dominant_stage": dominant.get("lifecycle_stage"),
            "dominant_channel": dominant.get("preferred_channel"),
            "top_tags": tags,
            "top_terms": keywords,
            "criteria": criteria,
            "subtitle": " · ".join(f"{item['label']}: {item['value']}" for item in criteria[:3]),
            "avg_engagement_score": avg_engagement,
        },
        "explanation": {
            "reason": build_reason(criteria, keywords),
            "dominant_fields": dominant,
            "keywords": keywords,
            "top_tags": tags,
            "criteria": criteria,
        },
    }


def main():
    payload = json.load(sys.stdin)
    rows = payload.get("dataset", [])
    max_clusters = int(payload.get("max_clusters", 6))

    if len(rows) < 2:
        json.dump(
            {
                "algorithm": payload.get("algorithm", "kmeans"),
                "model_version": payload.get("model_version", "kmeans-v1"),
                "clusters": [],
                "outliers_count": len(rows),
                "metrics": {"reason": "insufficient_contacts"},
            },
            sys.stdout,
        )
        return

    assignments, centroids, vectors = kmeans(rows, max_clusters)
    clusters = []
    outliers_count = 0

    for cluster_idx, indices in enumerate(assignments):
        if len(indices) < 2:
            outliers_count += len(indices)
            continue

        member_rows = [rows[idx] for idx in indices]
        summary = summarize_cluster(member_rows)
        members = []
        cohesion_distances = []

        for rank, row_idx in enumerate(indices, start=1):
            row = rows[row_idx]
            dist = distance(vectors[row_idx], centroids[cluster_idx])
            cohesion_distances.append(dist)
            members.append(
                {
                    "contact_id": row["contact_id"],
                    "membership_score": round(max(0.0, 1.0 - dist), 4),
                    "explanation": {
                        "distance_to_centroid": round(dist, 4),
                        "matched_on": summary["explanation"].get("dominant_fields", {}),
                        "top_terms": (row.get("features", {}) or {}).get("text_terms", [])[:4],
                        "top_tags": (row.get("features", {}) or {}).get("tags", [])[:3],
                    },
                }
            )

        cohesion_score = round(max(0.0, 1.0 - (sum(cohesion_distances) / max(1, len(cohesion_distances)))), 4)
        signature = "|".join(str(item["contact_id"]) for item in members) + "|" + summary["slug"]
        cluster_key = "py:" + hashlib.sha1(signature.encode("utf-8")).hexdigest()

        clusters.append(
            {
                "cluster_key": cluster_key,
                "name": summary["name"],
                "slug": summary["slug"],
                "cohesion_score": cohesion_score,
                "summary": summary["summary"],
                "explanation": summary["explanation"],
                "members": members,
            }
        )

    json.dump(
        {
            "algorithm": payload.get("algorithm", "kmeans"),
            "model_version": payload.get("model_version", "kmeans-v1"),
            "clusters": clusters,
            "outliers_count": outliers_count,
            "metrics": {
                "dataset_size": len(rows),
                "clusters_count": len(clusters),
                "mode": "python_worker",
            },
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
