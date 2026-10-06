{{/* Fully-qualified image refs.
     If image.<svc>.image is set (Argo Image Updater write-back via
     helm.image-spec — it owns the whole ref incl. :tag or @sha256 digest),
     use it verbatim; otherwise compose registry/repo:tag. */}}
{{- define "app.image.backend" -}}
{{- if .Values.image.backend.image }}{{ .Values.image.backend.image }}{{- else }}{{ .Values.image.registry }}/{{ .Values.image.backend.repo }}:{{ .Values.image.backend.tag }}{{- end }}
{{- end -}}

{{- define "app.image.frontend" -}}
{{- if .Values.image.frontend.image }}{{ .Values.image.frontend.image }}{{- else }}{{ .Values.image.registry }}/{{ .Values.image.frontend.repo }}:{{ .Values.image.frontend.tag }}{{- end }}
{{- end -}}

{{/* Common labels */}}
{{- define "app.labels" -}}
app.kubernetes.io/part-of: app
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* envFrom shared by every app workload: .env Secret first, topology CM last
     (so chart-forced topology keys win over the .env Secret). */}}
{{- define "app.envFrom" -}}
- secretRef:
    name: app-dotenv
- configMapRef:
    name: app-env
{{- end -}}

{{/* DB credentials from the CNPG-generated Secret db-app. `env` beats
     envFrom, so these win over anything in app-dotenv. */}}
{{- define "app.dbEnv" -}}
- { name: POSTGRES_USER, valueFrom: { secretKeyRef: { name: db-app, key: username } } }
- { name: POSTGRES_PASSWORD, valueFrom: { secretKeyRef: { name: db-app, key: password } } }
{{- end -}}

{{/* optional imagePullSecrets */}}
{{- define "app.pullSecrets" -}}
{{- if .Values.image.pullSecret }}
imagePullSecrets:
  - name: {{ .Values.image.pullSecret }}
{{- end }}
{{- end -}}

{{/* wait-for-infra initContainer (pgbouncer + redis) */}}
{{- define "app.waitForInfra" -}}
- name: wait-for-infra
  image: busybox:1.36
  command: ["sh", "-c", "until nc -z pgbouncer 5432; do sleep 2; done; until nc -z redis 6379; do sleep 2; done"]
{{- end -}}
