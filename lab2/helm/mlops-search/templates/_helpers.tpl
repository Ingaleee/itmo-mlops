{{- define "mlops-search.name" -}}
{{- printf "%s-mlops-search" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mlops-search.digest" -}}
{{- $digest := required "image.digest is required; use sha256 followed by 64 hexadecimal characters" .Values.image.digest -}}
{{- if not (regexMatch "^sha256:[0-9a-f]{64}$" $digest) -}}
{{- fail "image.digest must match sha256:[0-9a-f]{64}" -}}
{{- end -}}
{{- $digest -}}
{{- end -}}

{{- define "mlops-search.image" -}}
{{- $repository := required "image.repository is required" .Values.image.repository -}}
{{- if or (contains "@" $repository) (regexMatch ":[^/]+$" $repository) -}}
{{- fail "image.repository must not include a tag or digest" -}}
{{- end -}}
{{- printf "%s@%s" $repository (include "mlops-search.digest" .) -}}
{{- end -}}

{{- define "mlops-search.labels" -}}
app.kubernetes.io/name: mlops-search
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
