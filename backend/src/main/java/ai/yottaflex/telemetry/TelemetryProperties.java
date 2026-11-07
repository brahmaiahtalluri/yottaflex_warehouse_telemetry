package ai.yottaflex.telemetry;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "telemetry")
public class TelemetryProperties {

    private String dataDir = "../data/seed";
    private String workflowJournal = "data/runtime/workflow-events.jsonl";

    public String getDataDir() {
        return dataDir;
    }

    public void setDataDir(String dataDir) {
        this.dataDir = dataDir;
    }

    public String getWorkflowJournal() {
        return workflowJournal;
    }

    public void setWorkflowJournal(String workflowJournal) {
        this.workflowJournal = workflowJournal;
    }
}
