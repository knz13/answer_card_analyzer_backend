



class WebsocketMessageCommand:
    READ_TO_IMAGES = "readToImages"
    IDENTIFY_CIRCLES = "identifyCircles"
    GET_CALIBRATION = "getCalibration"
    FIND_CIRCLES = "findCircles"

class WebsocketMessageStatus:
    COMPLETED_TASK = "completedTask"
    ERROR = "error"
    PROGRESS = "progress"

class BoxRectangleType:
    TYPE_B = "Tipo B"
    COLUMN_QUESTIONS = "Coluna de Questões (A e C PAS ou Enem)"
    MATRICULA = "Matricula"
    OUTRO = "Outro"
    TEMP = "Temp"
    EXEMPLO_CIRCULO = "Exemplo de Círculo"